# Cold start and cost of serverless ML inference on AWS Lambda: ARM64 versus x86

Measurement code, infrastructure templates and raw logs for a full-factorial benchmark of ML inference on AWS Lambda. The factors are model size, architecture (arm64 / x86_64), packaging (zip / container image) and memory (512–10,240 MB).

## Layout

| Path | Content |
|---|---|
| `src/handler.py` | Lambda handler; imports and model loading run in the INIT phase |
| `infra/template.yaml` | AWS SAM template, one configuration per stack (function, role, log group) |
| `scripts/fetch_model.sh` | Downloads the model files and checks their SHA-256 |
| `scripts/build_zip.sh` | Builds the zip package for a model and an architecture |
| `scripts/deploy.sh` | Uploads the package and deploys one configuration |
| `scripts/cleanup.sh` | Deletes every project resource and verifies that nothing is left |
| `bench/driver.py` | Forced cold starts and warm invocations; writes raw JSONL |
| `bench/analyze.py` | Parses REPORT lines; computes Table 1/2 fields, bootstrap CIs and cost |
| `bench/prices.json` | Dated AWS Lambda list prices |
| `data/raw/` | Unchanged driver output and CloudWatch REPORT exports |
| `data/processed/` | Parsed invocations and per-configuration summaries |
| `docs/` | Pilot report and deviation log |

## Reproduce one configuration

```bash
python3.11 -m venv .venv && .venv/bin/pip install boto3 numpy
scripts/fetch_model.sh m3_distilbert       # downloads and verifies SHA-256
scripts/build_zip.sh m3_distilbert x86_64
scripts/deploy.sh m3_distilbert x86_64 512
.venv/bin/python bench/driver.py --function-name citf7001-m3-x86-zip-512 \
    --config-id m3-x86-zip-512 --cold 30 --warm 100 --out data/raw/<file>.jsonl
.venv/bin/python bench/analyze.py data/raw/*.jsonl --out-dir data/processed
scripts/cleanup.sh            # always run; prints RESULT: CLEAN when nothing is left
```

AWS credentials come from the profile set in `scripts/env.sh` (default `personal`); the region defaults to `eu-central-1`.
