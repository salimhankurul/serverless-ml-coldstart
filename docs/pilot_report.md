# Pilot report – configuration m3-x86-zip-512

**Configuration:** DistilBERT int8 (ONNX) · x86_64 · zip package · 512 MB  
**Run:** `20261117T222337Z-b94eb0`, 2026-11-17 22:23:41–22:25:56 UTC (2026-11-18, 01:23–01:26 Istanbul time), AWS Lambda eu-central-1  
**Stack:** python3.12 runtime, ONNX Runtime 1.32.0, tokenizers 0.23.3, numpy 2.5.5; package 95.2 MB zipped / 207 MB unzipped; model SHA-256 `79b45c7f…29c94f7f` (full hash in `docs/deviation_log.md`)  
**Protocol:** as registered. After deployment, one invocation was discarded. Each cold start was forced by changing an environment variable, waiting for `LastUpdateStatus = Successful`, then invoking once. That gave 30 cold starts, followed by 100 sequential warm invocations. REPORT lines were captured from the invoke log tail and cross-checked against a CloudWatch export (131/131 lines identical).

## Raw REPORT lines (first three cold, first three warm; all 131 in `data/raw/`)

```
2026-11-17T22:23:45.745Z cold  REPORT RequestId: 3c697357-d6f3-4521-a637-cc247e8f960d  Duration: 175.17 ms  Billed Duration: 1991 ms  Memory Size: 512 MB  Max Memory Used: 254 MB  Init Duration: 1815.38 ms
2026-11-17T22:23:49.775Z cold  REPORT RequestId: d2756bfa-be12-4eb3-9df1-e29810c74d04  Duration: 123.73 ms  Billed Duration: 1940 ms  Memory Size: 512 MB  Max Memory Used: 273 MB  Init Duration: 1815.34 ms
2026-11-17T22:23:53.992Z cold  REPORT RequestId: 1214d8e0-1d2d-4fba-ac53-3b2c9fd9dbf3  Duration: 111.61 ms  Billed Duration: 1942 ms  Memory Size: 512 MB  Max Memory Used: 273 MB  Init Duration: 1829.78 ms
2026-11-17T22:25:43.051Z warm  REPORT RequestId: b3fb2543-5f8c-4653-9655-980fca3e0fbb  Duration: 90.45 ms  Billed Duration: 91 ms  Memory Size: 512 MB  Max Memory Used: 273 MB
2026-11-17T22:25:43.172Z warm  REPORT RequestId: cbf5322e-1342-475e-b2f9-0d08a8cd46b3  Duration: 58.73 ms  Billed Duration: 59 ms  Memory Size: 512 MB  Max Memory Used: 273 MB
2026-11-17T22:25:43.292Z warm  REPORT RequestId: 468e2e87-97c7-4bc9-a095-9183bed59227  Duration: 62.56 ms  Billed Duration: 63 ms  Memory Size: 512 MB  Max Memory Used: 273 MB
```

## Parsed row (Table 1 / Table 2 fields, from `data/processed/summary.csv`)

| n cold / warm | Cold p50 [95 % CI] | Cold p95 | Warm p50 | Warm p95 | Warm p99 | Cost / 1,000 req, c = 1 % | c = 10 % | Meets T |
|---|---|---|---|---|---|---|---|---|
| 30 / 100 | 1,942.8 ms [1,936.1; 1,956.0] | 2,062.5 ms | 62.5 ms | 97.4 ms | 105.8 ms | USD 0.00093 | USD 0.00234 | yes |

Cold start = Init Duration + Duration of the first invocation. The CI is a percentile bootstrap with 10,000 resamples and seed 20261118. Percentiles use linear interpolation. T is cold p50 ≤ 2,000 ms and warm p95 ≤ 200 ms.

## Actual cost

| Item | Usage | Cost at list price (eu-central-1, retrieved 2026-11-08) |
|---|---|---|
| 131 measured invocations | 67.045 billed s × 0.5 GB = 33.52 GB-s, plus 131 requests | USD 0.000585 |
| 1 smoke-test invocation before the run | 0.97 GB-s | USD 0.000016 |
| S3 artifact (95 MB, about 4 min) and CloudWatch Logs (about 40 KB) | – | below USD 0.0001 |
| **Pilot total** | | **≈ USD 0.0006** |

The amount actually invoiced can be read in the AWS Billing console 24–48 h after the run. It may show USD 0.00 if the free tier covers it.

## What the pilot showed

1. **No slow initialisations at 512 MB.** Init Duration ranged from 1,478 to 1,935 ms (median 1,809 ms), well below Lambda's 10 s INIT limit. All 30 forced cold starts produced an Init Duration on the first attempt, so none were lost to proactive initialisation.
2. **The INIT phase is billed.** In 30/30 cold starts, Billed Duration equals Init Duration + Duration rounded up to the next millisecond. This confirms the August 2025 billing change for zip functions.
3. **The pilot configuration sits right at the target.** Cold p50 is 1,943 ms (CI upper bound 1,956 ms), just below the 2,000 ms target, while cold p95 (2,063 ms) would fail a p95 criterion. Selection near the threshold is therefore sensitive, which supports reporting bootstrap selection stability.
4. **Cold start seen by the client is larger than Init + Duration.** The median client-side cold latency was 2,517 ms, about 573 ms above Init + Duration. Placement and code loading are not part of Init Duration, plus network time. This is reported as a secondary outcome, as planned.
5. **Where INIT time goes** (measured inside the function): importing libraries took a median of 663 ms; loading the tokenizer and model took 1,057 ms. The first inference took 95 ms, against 40 ms on warm invocations, which suggests lazy initialisation in ONNX Runtime.
6. **Cost assumptions were conservative for this configuration.** The billed cold start was about 1.96 s, against the 10 s upper bound; warm calls were about 63 ms, against the assumed 0.3 s.
7. **ONNX Runtime 1.32 logs a telemetry warning** ("Failed to persist telemetry device ID") during every INIT and never in warm calls. Decision: keep the default settings for all 60 configurations (deviation log #9).

## Clean-up

The stack (function, IAM role, log group), the artifact bucket and the stack-managed log group were deleted with `scripts/cleanup.sh`. Its verification found no project resources left. A full inventory of the account taken after clean-up is identical to the inventory taken before the pilot.
