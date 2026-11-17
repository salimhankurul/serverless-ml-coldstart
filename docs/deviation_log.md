# Deviation log

All changes to the registered methodology (midterm file, 8 November 2026), with date and reason.

| # | Date | What changed | Why | Effect on results |
|---|---|---|---|---|
| 1 | 2026-11-18 (before pilot) | RQ3 cold-start criterion changed from cold p95 ≤ 2,000 ms to **cold p50 ≤ 2,000 ms**; warm p95 ≤ 200 ms unchanged; bootstrap selection stability added to the report | Supervisor's feedback: p95 at n = 30 was called unreliable, yet used in T. Fixed by e-mail before the pilot ran | Target only; no data existed yet |
| 2 | 2026-11-18 (before pilot) | Cost-estimate upper bound raised from 3 s to 10 s per cold start | [23] reports 9.08 s (TF) / 2.78 s (ORT) at 2 GB; 3 s does not bound 512 MB | Estimate only (≈ USD 1.10, or USD 3.20 with reruns) |
| 3 | 2026-11-18 (pilot) | Measurement driver ran on the author's laptop (Istanbul) instead of in-region (CloudShell/EC2) | Pilot set-up | Platform metrics (Init Duration, Duration) unaffected; client-side latency includes WAN time (warm: client − Duration ≈ 61 ms median). For the factorial, run the driver in-region or report client latency with this caveat |
| 4 | 2026-11-18 (pilot) | Lambda log format **Text** instead of JSON; REPORT lines captured from the invoke log tail (`LogType=Tail`) and cross-checked with a CloudWatch export | The Text REPORT line is the raw line requested for the pilot | None (131/131 lines identical in both sources) |
| 5 | 2026-11-18 (pilot) | SAM template deployed with `aws cloudformation deploy` (server-side SAM transform) instead of the SAM CLI | SAM CLI not needed for zip packages stored in S3 | None |
| 6 | 2026-11-18 (pilot) | onnxruntime and tokenizers installed with `--no-deps` (only numpy added) | Optional dependencies (sympy, protobuf, huggingface_hub …) pushed the package over the 250 MB unzipped limit; they are not imported at inference time | None on inference; package 207 MB unzipped |
| 7 | 2026-11-18 (pilot) | One smoke-test invocation before the pilot run | Check that the package imports on Lambda | Not part of the data set; its REPORT line is in the CloudWatch export |
| 8 | 2026-11-18 (after pilot) | The AWS Budgets alarm (USD 10 per month, e-mail at 80 % actual and 100 % forecast) described in the midterm as already set was created only now | It had not been created before the pilot | None. Pilot cost ≈ USD 0.0006; the alarm is in place before the factorial |
| 9 | 2026-11-18 (after pilot) | Decision: ONNX Runtime is used with its default settings, telemetry included | Measures the out-of-the-box stack that practitioners deploy. The warning comes from the read-only file system, and the pilot showed no heavy tail (Init max 1,935 ms vs median 1,809 ms) | Applied identically to all 60 configurations |

## Model provenance

- M3: `Xenova/distilbert-base-uncased-finetuned-sst-2-english`, file `onnx/model_quantized.onnx` (int8, 67,581,197 bytes), Hugging Face, downloaded 2026-11-18.
  SHA-256 `79b45c7fd8c2673aa53615aba07caeb2de798f63a95a2393a365982429c94f7f`; `tokenizer.json` SHA-256 `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`.

