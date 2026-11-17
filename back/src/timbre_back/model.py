"""A model version's Fit, on top of the frozen multilingual-e5-small vectors.

Fit = (1 - head_weight) * cosine(projection of the Description vector, Song vector)
    + head_weight * (1 - mean |predicted labels - Song labels|)

where the labels are the Song's AcousticBrainz class probabilities
(catalog.songs.labels, in profile.WORDS order) and the head predicts them from the
Description vector. A Song without labels gets the cosine alone. The baseline
(version 1, no file) is the plain e5 cosine. Trained versions are .npz files on the
models volume (MODEL_DIR), written once by the train job and never changed.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from timbre_back.db import vector_literal
from timbre_back.profile import WORDS

MODEL_DIR = Path(os.environ.get("OWN_MODEL_DIR", "/models/own"))
DIMS = 384
LABELS = len(WORDS)

Floats = npt.NDArray[np.float32]


class Model(NamedTuple):
    projection: Floats  # (DIMS, DIMS): projected = description @ projection
    head: Floats  # (DIMS, LABELS): labels = clip(description @ head + bias, 0, 1)
    bias: Floats  # (LABELS,)
    head_weight: float

    def project(self, descriptions: Floats) -> tuple[Floats, Floats]:
        """The projected (unit) Description vectors and their predicted labels."""
        projected = descriptions @ self.projection
        projected /= np.linalg.norm(projected, axis=1, keepdims=True)
        return projected, np.clip(descriptions @ self.head + self.bias, 0, 1)

    def fit(self, descriptions: Floats, vectors: Floats, labels: Floats) -> Floats:
        """Fit of each Description (row) with each Song (column), as SEARCH_SQL has it.

        A Song without labels (a NaN row) gets the projection's cosine alone.
        """
        projected, predicted = self.project(descriptions)
        cosine = projected @ vectors.T
        if not self.head_weight:
            return cosine
        distance = np.stack([np.abs(labels - p).mean(axis=1) for p in predicted])
        fit: Floats = np.where(
            np.isnan(distance),
            cosine,
            (1 - self.head_weight) * cosine + self.head_weight * (1 - distance),
        ).astype(np.float32)
        return fit

    def search_params(self, description: list[float]) -> dict[str, object]:
        """SEARCH_SQL's model parameters for one Description vector."""
        projected, predicted = self.project(np.array([description], dtype=np.float32))
        return {
            "vector": vector_literal(projected[0].tolist()),
            "labels": vector_literal(predicted[0].tolist()),
            "head_weight": self.head_weight,
        }

    def save(self, file: str) -> None:
        """Write to MODEL_DIR, all at once: a reader never sees half a file."""
        tmp = MODEL_DIR / f".{file}.tmp"
        with tmp.open("wb") as f:
            np.savez(
                f,
                projection=self.projection,
                head=self.head,
                bias=self.bias,
                head_weight=self.head_weight,
            )
        tmp.replace(MODEL_DIR / file)


BASELINE = Model(
    np.eye(DIMS, dtype=np.float32),
    np.zeros((DIMS, LABELS), dtype=np.float32),
    np.zeros(LABELS, dtype=np.float32),
    0.0,
)


@lru_cache(maxsize=4)
def load(file: str | None) -> Model:
    """The model of a version's file; None is the baseline. Files never change."""
    if file is None:
        return BASELINE
    with np.load(MODEL_DIR / file) as f:
        return Model(f["projection"], f["head"], f["bias"], float(f["head_weight"]))
