"""Parser test on REPORT lines in the documented AWS Lambda text log format."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
from analyze import parse_report  # noqa: E402

COLD = ("REPORT RequestId: 6c5f6b2e-1111-2222-3333-444455556666\tDuration: 12.34 ms\t"
        "Billed Duration: 1580 ms\tMemory Size: 512 MB\tMax Memory Used: 201 MB\tInit Duration: 1567.10 ms\t")
WARM = ("REPORT RequestId: 7d6f7c3f-1111-2222-3333-444455556666\tDuration: 9.87 ms\t"
        "Billed Duration: 10 ms\tMemory Size: 512 MB\tMax Memory Used: 202 MB\t")


def test_cold():
    r = parse_report(COLD)
    assert r == {"duration_ms": 12.34, "billed_ms": 1580.0, "memory_mb": 512.0,
                 "max_memory_used_mb": 201.0, "init_ms": 1567.10}


def test_warm():
    r = parse_report(WARM)
    assert r["duration_ms"] == 9.87 and r["billed_ms"] == 10.0 and r["init_ms"] is None


if __name__ == "__main__":
    test_cold(); test_warm(); print("parser tests passed")
