"""The train job: `python -m timbre_back.train` queues it.

Trains a model version (see model.py) on top of the frozen e5 vectors, on CPU, from the
drafted pairs (training_drafted.json, every Song a positive) and visitor Feedback (👍
positives, 👎 hard negatives). Benchmark Descriptions, and Descriptions close to one,
never reach training (may_train_on). The job then scores the new version on the
Benchmark, tuning its cutoff and Popularity weight, records it, and promotes it if its
score is not worse than the promoted version's, scored the same way now.
"""

import asyncio
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import numpy as np
import psycopg
from psycopg.types.json import Jsonb

from timbre_back import benchmark
from timbre_back import model as models
from timbre_back.db import conninfo
from timbre_back.embed import embed_query
from timbre_back.feedback import normalize
from timbre_back.model import DIMS, LABELS, Floats, Model

log = logging.getLogger("timbre.train")
FILES = [Path(__file__).with_name("training_drafted.json")]
NEAR = 0.92  # e5 cosine to a Benchmark Description that keeps a Description out
# Fixed by hand, not tuned on the Benchmark (owner-approved).
# Ridge strengths: the projection is pulled toward the identity (plain e5), the head
# toward predicting the average labels.
PROJECTION_RIDGE = 1.0
HEAD_RIDGE = 1.0
NEGATIVE_WEIGHT = 0.5  # how far a 👎 Song moves its Description's target away
HEAD_WEIGHT = 0.2  # the head's share of Fit
MARGIN = 0.05  # a 👎 Song's Fit must end at least this far below its 👍 Songs'
HINGE_STEPS = 200
HINGE_RATE = 1.0

# normalized Description -> (positive Song IDs, hard negative Song IDs)
Examples = dict[str, tuple[list[str], list[str]]]


def examples(votes: Iterable[tuple[str, str, str]]) -> Examples:
    """Group (Description, Song ID, "up"/"down") by normalized Description."""
    grouped: Examples = {}
    for description, song_id, vote in votes:
        up, down = grouped.setdefault(normalize(description), ([], []))
        (up if vote == "up" else down).append(song_id)
    return grouped


def may_train_on(
    descriptions: list[str],
    vectors: Floats,
    benchmark_descriptions: list[str],
    benchmark_vectors: Floats,
) -> list[bool]:
    """Per Description, whether training may use it: not if it is a Benchmark
    Description or within NEAR e5 cosine of one (so no Benchmark expected pair)."""
    taken = {normalize(d) for d in benchmark_descriptions}
    near = (vectors @ benchmark_vectors.T).max(axis=1, initial=-1.0) >= NEAR
    return [d not in taken and not n for d, n in zip(descriptions, near, strict=True)]


def fit_model(
    descriptions: Floats,
    targets: Floats,
    label_descriptions: Floats,
    label_targets: Floats,
) -> Model:
    """Ridge regressions, closed form: the projection maps each Description vector to
    its target, the head maps it to its positives' average labels."""
    eye = np.eye(DIMS)
    projection = np.linalg.solve(
        descriptions.T @ descriptions + PROJECTION_RIDGE * eye,
        descriptions.T @ targets + PROJECTION_RIDGE * eye,
    ).astype(np.float32)
    if not len(label_descriptions):
        return models.BASELINE._replace(projection=projection)
    mean_description = label_descriptions.mean(axis=0)
    mean_labels = label_targets.mean(axis=0)
    centered = label_descriptions - mean_description
    head = np.linalg.solve(
        centered.T @ centered + HEAD_RIDGE * eye,
        centered.T @ (label_targets - mean_labels),
    )
    return Model(
        projection,
        head.astype(np.float32),
        (mean_labels - mean_description @ head).astype(np.float32),
        HEAD_WEIGHT,
    )


class Triples(NamedTuple):
    """(Description, 👍 Song, 👎 Song) for the same Description, one per row."""

    descriptions: Floats
    up_vectors: Floats
    up_labels: Floats  # NaN rows: no labels
    down_vectors: Floats
    down_labels: Floats


def push_negatives(model: Model, triples: Triples) -> Model:
    """Hard negatives: gradient steps on a hinge loss, projection and head both, until
    every 👎 Song's Fit is MARGIN below its Description's 👍 Song's (as Model.fit)."""
    if not len(triples.descriptions):
        return model
    x = triples.descriptions.astype(np.float64)
    projection = model.projection.astype(np.float64)
    head = model.head.astype(np.float64)
    bias = model.bias.astype(np.float64)
    alpha = model.head_weight
    sides = []
    for vectors, labels in (
        (triples.up_vectors, triples.up_labels),
        (triples.down_vectors, triples.down_labels),
    ):
        has = ~np.isnan(labels).any(axis=1, keepdims=True)
        # weights of cosine and head in Fit: the cosine alone without labels
        sides.append(
            (vectors, np.nan_to_num(labels), np.where(has, 1 - alpha, 1.0), has * alpha)
        )
    for _ in range(HINGE_STEPS):
        projected = x @ projection
        norm = np.linalg.norm(projected, axis=1, keepdims=True)
        unit = projected / norm
        raw = x @ head + bias
        predicted = np.clip(raw, 0, 1)
        fits, d_unit, d_head = [], [], []
        for vectors, labels, w_cosine, w_head in sides:
            cosine = (unit * vectors).sum(axis=1, keepdims=True)
            difference = predicted - labels
            distance = np.abs(difference).mean(axis=1, keepdims=True)
            fits.append(w_cosine * cosine + w_head * (1 - distance))
            d_unit.append(w_cosine * (vectors - cosine * unit) / norm)
            inside = (raw > 0) & (raw < 1)  # where the clip lets a gradient through
            d_head.append(-w_head * np.sign(difference) / LABELS * inside)
        violated = fits[0] - fits[1] < MARGIN
        if not violated.any():
            break
        share = violated / len(x)  # the loss is a mean over the triples
        # The loss is MARGIN + Fit(👎) - Fit(👍) over the violated triples.
        grad_projected = (d_unit[1] - d_unit[0]) * share
        grad_head = (d_head[1] - d_head[0]) * share
        projection -= HINGE_RATE * x.T @ grad_projected
        head -= HINGE_RATE * x.T @ grad_head
        bias -= HINGE_RATE * grad_head.sum(axis=0)
    return model._replace(
        projection=projection.astype(np.float32),
        head=head.astype(np.float32),
        bias=bias.astype(np.float32),
    )


def learn(
    grouped: Examples, vectors: Floats, usable: list[bool], catalog: benchmark.Catalog
) -> tuple[Model, int, int]:
    """The model for the usable Descriptions (their e5 vectors in `vectors`), and how
    many Descriptions and how many with labels it learned from."""
    index = {song_id: i for i, song_id in enumerate(catalog.song_ids)}
    rows: list[tuple[Floats, Floats]] = []
    label_rows: list[tuple[Floats, Floats]] = []
    triples: list[tuple[Floats, int, int]] = []
    for description, vector, ok in zip(grouped, vectors, usable, strict=True):
        up, down = (
            [index[s] for s in songs if s in index] for songs in grouped[description]
        )
        if not ok or not (up or down):
            continue
        # Without a positive, the Description keeps its own vector and only moves away.
        target = catalog.vectors[up].mean(axis=0) if up else vector
        if down:
            target = target - NEGATIVE_WEIGHT * catalog.vectors[down].mean(axis=0)
        rows.append((vector, target / np.linalg.norm(target)))
        labels = catalog.labels[up]
        labels = labels[~np.isnan(labels).any(axis=1)]
        if len(labels):
            label_rows.append((vector, labels.mean(axis=0)))
        # shortcut: a 👎 without a 👍 on its Description only moves the target; pair
        # it with the Description's other top Matches if such votes become common.
        triples.extend((vector, u, d) for u in up for d in down)
    if not rows:
        raise ValueError("no training pairs left after excluding the Benchmark")
    model = fit_model(
        np.array([v for v, _ in rows]),
        np.array([t for _, t in rows]),
        np.array([v for v, _ in label_rows]).reshape(-1, DIMS),
        np.array([t for _, t in label_rows]).reshape(-1, LABELS),
    )
    ups = [u for _, u, _ in triples]
    downs = [d for _, _, d in triples]
    model = push_negatives(
        model,
        Triples(
            np.array([v for v, _, _ in triples]).reshape(-1, DIMS),
            catalog.vectors[ups],
            catalog.labels[ups],
            catalog.vectors[downs],
            catalog.labels[downs],
        ),
    )
    return model, len(rows), len(label_rows)


def drafted() -> list[tuple[str, str, str]]:
    return [
        (e["description"], s["id"], "up")
        for f in FILES
        for e in json.loads(f.read_text())
        for s in e["songs"]
    ]


async def train(conn: psycopg.AsyncConnection) -> None:
    bench = await benchmark.read(conn)
    if bench is None:
        log.warning("train: skipped, no Song has a vector yet (build-vectors)")
        return
    cur = await conn.execute(
        "SELECT description, song_id::text, vote FROM feedback.votes"
    )
    grouped = examples([*drafted(), *await cur.fetchall()])
    vectors = np.array(
        await asyncio.to_thread(lambda: [embed_query(d) for d in grouped]),
        dtype=np.float32,
    ).reshape(-1, DIMS)
    usable = may_train_on(
        list(grouped), vectors, bench.descriptions, bench.description_vectors
    )
    candidate, trained, labelled = await asyncio.to_thread(
        learn, grouped, vectors, usable, bench.catalog
    )

    cur = await conn.execute(
        "SELECT id, file FROM catalog.model_versions WHERE promoted"
    )
    promoted = await cur.fetchone()
    if promoted is None:
        raise ValueError("no promoted model version to compare with")
    current, *_ = await benchmark.tuned(conn, models.load(promoted[1]), bench)
    scores, cutoff, weight = await benchmark.tuned(conn, candidate, bench)
    promote = scores.recall >= current.recall

    # A sequence: two runs never share an id, so never a file either.
    cur = await conn.execute(
        "SELECT nextval(pg_get_serial_sequence('catalog.model_versions', 'id'))"
    )
    (version,) = await cur.fetchone() or (None,)
    file = f"{version}.npz"
    await asyncio.to_thread(candidate.save, file)
    if promote:
        await conn.execute(
            "UPDATE catalog.model_versions SET promoted = false WHERE promoted"
        )
    await conn.execute(
        "INSERT INTO catalog.model_versions (id, name, benchmark_score, cutoff,"
        " popularity_weight, promoted, file, recall_at_24, precision_at_16)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            version,
            f"own v{version}",
            scores.recall,
            cutoff,
            weight,
            promote,
            file,
            Jsonb(scores.recall_by_file),
            Jsonb(scores.precision_by_file),
        ),
    )
    log.info(
        "train: %d Descriptions (%d excluded as Benchmark or near it), %d with labels."
        " Version %d scores %.3f at cutoff %.3f and weight %.3f; the promoted"
        " version %d scores %.3f now. %s Version %d: %s",
        trained,
        usable.count(False),
        labelled,
        version,
        scores.recall,
        cutoff,
        weight,
        promoted[0],
        current.recall,
        "Promoted." if promote else "Not promoted: worse.",
        version,
        benchmark.report(scores),
    )


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        await conn.execute("INSERT INTO jobs.queue (kind) VALUES ('train')")


if __name__ == "__main__":
    asyncio.run(main())
