"""AWS Lambda handler for the cold-start benchmark: text classification with an ONNX model.

Everything that belongs to the cold start (library import, tokenizer and model loading)
runs at module level, i.e. in the Lambda INIT phase. No warm-up inference is run.
"""
import os
import time

_t0 = time.perf_counter()
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
from tokenizers import Tokenizer  # noqa: E402

_t_import = time.perf_counter()

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
_tokenizer = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
_tokenizer.enable_truncation(max_length=128)
_session = ort.InferenceSession(
    os.path.join(MODEL_DIR, "model.onnx"), providers=["CPUExecutionProvider"]
)
_input_names = {i.name for i in _session.get_inputs()}
_t_load = time.perf_counter()

INIT_INFO = {
    "import_ms": round((_t_import - _t0) * 1000, 2),
    "load_ms": round((_t_load - _t_import) * 1000, 2),
    "ort_version": ort.__version__,
    "numpy_version": np.__version__,
    "cpu_count": os.cpu_count(),
}
_invocations = 0

DEFAULT_TEXT = "The service answered quickly and the result was correct."


def lambda_handler(event, context):
    global _invocations
    _invocations += 1
    text = (event or {}).get("text", DEFAULT_TEXT)
    enc = _tokenizer.encode(text)
    feeds = {
        "input_ids": np.array([enc.ids], dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
    }
    feeds = {k: v for k, v in feeds.items() if k in _input_names}
    t = time.perf_counter()
    logits = _session.run(None, feeds)[0][0]
    infer_ms = (time.perf_counter() - t) * 1000
    return {
        "label": int(np.argmax(logits)),
        "infer_ms": round(infer_ms, 3),
        "invocation_in_env": _invocations,
        **INIT_INFO,
    }
