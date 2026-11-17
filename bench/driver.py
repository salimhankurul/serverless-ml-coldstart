"""Measurement driver: forced cold starts and warm invocations for one Lambda configuration.

Protocol (registered in the methodology file):
  * Discard the first invocation after a deployment.
  * Cold start: change a dummy environment variable -> wait until LastUpdateStatus is
    Successful -> invoke once. The invocation counts as cold only if its REPORT line
    contains "Init Duration"; other attempts are kept in the raw log and counted.
  * Warm: after the cold block, sequential invocations; warm only without "Init Duration".
Every invocation is written unchanged (REPORT line, log tail, response) to a JSONL file.
"""
import argparse
import base64
import json
import re
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config

REPORT_RE = re.compile(r"^REPORT RequestId:.*$", re.MULTILINE)


def invoke(client, function_name, payload):
    t0 = time.perf_counter()
    resp = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps(payload).encode(),
    )
    body = resp["Payload"].read()
    client_ms = (time.perf_counter() - t0) * 1000
    tail = base64.b64decode(resp.get("LogResult", "")).decode("utf-8", "replace")
    m = REPORT_RE.search(tail)
    return {
        "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "request_id": resp["ResponseMetadata"]["HTTPHeaders"].get("x-amzn-requestid"),
        "status_code": resp["StatusCode"],
        "function_error": resp.get("FunctionError"),
        "client_ms": round(client_ms, 3),
        "report_line": m.group(0).rstrip() if m else None,
        "log_tail": tail,
        "response": body.decode("utf-8", "replace"),
    }


def force_new_environment(client, function_name):
    token = uuid.uuid4().hex
    client.update_function_configuration(
        FunctionName=function_name, Environment={"Variables": {"COLD_TOKEN": token}}
    )
    client.get_waiter("function_updated_v2").wait(
        FunctionName=function_name, WaiterConfig={"Delay": 1, "MaxAttempts": 120}
    )
    return token


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--function-name", required=True)
    ap.add_argument("--config-id", required=True)
    ap.add_argument("--cold", type=int, default=30, help="valid cold starts required")
    ap.add_argument("--warm", type=int, default=100)
    ap.add_argument("--max-cold-attempts", type=int, default=60)
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", default="personal")
    ap.add_argument("--region", default="eu-central-1")
    args = ap.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    client = session.client(
        "lambda", config=Config(read_timeout=180, retries={"max_attempts": 0})
    )
    fn_cfg = client.get_function_configuration(FunctionName=args.function_name)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    meta = {
        "run_id": run_id,
        "config_id": args.config_id,
        "function_name": args.function_name,
        "architecture": fn_cfg["Architectures"][0],
        "memory_mb": fn_cfg["MemorySize"],
        "runtime": fn_cfg["Runtime"],
        "code_size_bytes": fn_cfg["CodeSize"],
        "code_sha256": fn_cfg["CodeSha256"],
        "region": args.region,
    }

    seq = 0
    n_cold = n_cold_attempts = n_warm = n_warm_attempts = 0
    with open(args.out, "a", encoding="utf-8") as f:
        def write(phase, rec, **extra):
            nonlocal seq
            seq += 1
            row = {**meta, "seq": seq, "phase": phase, **extra, **rec}
            f.write(json.dumps(row) + "\n")
            f.flush()
            return row

        # Discard the first invocation after deployment.
        force_new_environment(client, args.function_name)
        write("discard_first_after_deploy", invoke(client, args.function_name, {}))

        while n_cold < args.cold and n_cold_attempts < args.max_cold_attempts:
            token = force_new_environment(client, args.function_name)
            rec = invoke(client, args.function_name, {})
            n_cold_attempts += 1
            is_cold = bool(rec["report_line"] and "Init Duration" in rec["report_line"])
            n_cold += is_cold
            write("cold" if is_cold else "cold_attempt_without_init", rec, cold_token=token)
            print(f"cold {n_cold}/{args.cold} (attempt {n_cold_attempts}) client={rec['client_ms']:.0f} ms "
                  f"{'' if is_cold else 'NO INIT DURATION'} {rec['function_error'] or ''}", flush=True)

        for _ in range(args.warm):
            rec = invoke(client, args.function_name, {})
            n_warm_attempts += 1
            is_warm = bool(rec["report_line"] and "Init Duration" not in rec["report_line"])
            n_warm += is_warm
            write("warm" if is_warm else "warm_attempt_with_init", rec)
        print(f"warm {n_warm}/{n_warm_attempts}", flush=True)

    print(json.dumps({"run_id": run_id, "cold": n_cold, "cold_attempts": n_cold_attempts,
                      "warm": n_warm, "warm_attempts": n_warm_attempts, "out": args.out}))


if __name__ == "__main__":
    main()
