"""multilingual-e5-small text vectors (384 dims, mean pooled, L2-normalised).

The ONNX export and tokenizer from the model's Hugging Face repo are baked into the
image at MODEL_DIR (see the Dockerfile). e5 needs "query: " / "passage: " prefixes.
"""

import os
from functools import cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/models/e5"))
MAX_TOKENS = 512


@cache
def _model() -> tuple[Tokenizer, ort.InferenceSession]:
    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    tokenizer.enable_truncation(MAX_TOKENS)
    tokenizer.enable_padding()
    session = ort.InferenceSession(
        str(MODEL_DIR / "model.onnx"), providers=["CPUExecutionProvider"]
    )
    return tokenizer, session


def _embed(texts: list[str]) -> list[list[float]]:
    tokenizer, session = _model()
    encodings = tokenizer.encode_batch(texts)
    ids = np.array([e.ids for e in encodings], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    (hidden,) = session.run(
        ["last_hidden_state"],
        {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": np.zeros_like(ids),
        },
    )
    summed = (hidden * mask[..., None]).sum(axis=1)
    mean = summed / mask.sum(axis=1, keepdims=True)
    unit = mean / np.linalg.norm(mean, axis=1, keepdims=True)
    return [[float(x) for x in row] for row in unit]


def embed_query(description: str) -> list[float]:
    return _embed([f"query: {description}"])[0]


def embed_passages(texts: list[str]) -> list[list[float]]:
    return _embed([f"passage: {t}" for t in texts])
