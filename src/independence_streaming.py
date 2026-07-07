"""Memory-safe, multi-core pairwise engine shared by the independence tests.

The classical independence tests compute an N x (N-1) impostor sweep. At La Salle
scale (756 pairs) that fits in memory trivially; at LFW scale (5,749 identities ->
33M ordered pairs, and larger for augmented sets) it does not. This module is the
one place that does the heavy sweep, and it is built to be:

* **Fast** - numpy-vectorised row-chunk distance kernels fanned out over a
  ``ProcessPoolExecutor`` (near-linear in core count).
* **OOM-safe** - the only things held in RAM are ``workers x chunk_rows`` distance
  buffers, a fixed-size top-K heap, and a bounded reservoir sample for plotting.
  Every pairwise distance is streamed to a float32 **memmap** on disk, so nothing
  that scales with the total comparison count lives in RAM.
* **Scalable** - ``workers`` scales with cores, ``chunk_rows`` / ``keep_top`` /
  ``sample_cap`` with RAM, ``device="gpu"`` swaps a CuPy kernel in for the distance
  math, and ``seg_start/seg_end`` shard a run across processes or machines.
* **Observable** - a live ``[COMPARE]`` progress bar (elapsed / eta / pair-rate).

Distances are computed over the **upper triangle only** (j > i): every unordered
impostor pair once. Because all metrics here are symmetric, the ordered N x (N-1)
distribution is just each unique distance twice, so unique-pair stats/percentiles
are identical and the ordered rank-k threshold maps to the ceil(k/2)-th unique pair
(handled by ``error_pair_report_from_topk``).
"""

from __future__ import annotations

import concurrent.futures
import heapq
import os
import sys
import tempfile
import time
from typing import Callable, Iterable, Sequence

import numpy as np

VALID_METRICS = ("chi2", "l2", "cosine")


# --------------------------------------------------------------------------- #
# Progress helpers
# --------------------------------------------------------------------------- #
def _fmt(seconds: float) -> str:
    secs = max(0, int(seconds))
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def _bar(done: int, total: int, width: int = 24) -> str:
    filled = int(width * done / total) if total > 0 else 0
    return "#" * filled + "-" * (width - filled)


# --------------------------------------------------------------------------- #
# Generic parallel map (used for per-image preprocessing at large N)
# --------------------------------------------------------------------------- #
def map_parallel(
    func: Callable,
    items: Sequence,
    *,
    workers: int = 6,
    desc: str = "WORK",
    progress: bool = True,
    chunksize: int = 8,
):
    """Run *func* over *items* on a process pool, preserving input order.

    Falls back to a plain serial map when ``workers <= 1`` (so the same code path
    works with no multiprocessing overhead for tiny inputs).
    """
    n = len(items)
    results = [None] * n
    start = time.time()

    if workers <= 1:
        for idx, item in enumerate(items):
            results[idx] = func(item)
            if progress and (idx + 1 == n or (idx + 1) % 50 == 0):
                _print_simple(desc, idx + 1, n, start)
        if progress:
            _print_simple(desc, n, n, start, final=True)
        return results

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
        completed = 0
        for idx, res in enumerate(ex.map(func, items, chunksize=chunksize)):
            results[idx] = res
            completed += 1
            if progress and (completed == n or completed % 50 == 0):
                _print_simple(desc, completed, n, start)
    if progress:
        _print_simple(desc, n, n, start, final=True)
    return results


def _print_simple(desc: str, count: int, total: int, start: float, *, final: bool = False) -> None:
    elapsed = time.time() - start
    rate = count / elapsed if elapsed > 0 else 0.0
    eta = (total - count) / rate if rate > 0 else 0.0
    pct = 100.0 * count / total if total else 0.0
    sys.stdout.write(
        f"\r[{desc}] [{_bar(count, total)}] {count}/{total} ({pct:6.2f}%) "
        f"| elapsed {_fmt(elapsed)} | eta {_fmt(eta)} | {rate:8.1f} it/s"
    )
    if final or count >= total:
        sys.stdout.write("\n")
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# Distance kernel (isolated so a GPU/CuPy swap is one place)
# --------------------------------------------------------------------------- #
def _distance_kernel(block, query, metric: str, xp):
    """Distance from every row of *block* (m, D) to *query* (D,).

    Smaller = more similar for all metrics (cosine -> 1 - cos). *xp* is ``numpy``
    or ``cupy``; the arithmetic is identical.
    """
    if metric == "chi2":
        diff = block - query
        denom = block + query + 1e-10
        return 0.5 * xp.sum((diff * diff) / denom, axis=1)
    if metric == "l2":
        diff = block - query
        return xp.sqrt(xp.einsum("ij,ij->i", diff, diff))
    if metric == "cosine":
        # Assumes rows are L2-normalised by the caller; 1 - cos in [0, 2].
        return 1.0 - block @ query
    raise ValueError(f"Unknown metric: {metric!r} (expected one of {VALID_METRICS})")


# --------------------------------------------------------------------------- #
# Worker process globals + task
# --------------------------------------------------------------------------- #
_W_FEATURES = None
_W_METRIC = "l2"
_W_BLOCK_ROWS = 384
_W_XP = None


def _close_memmap(mm) -> None:
    """Release a numpy memmap's underlying file handle (needed to unlink on Windows)."""
    try:
        base = getattr(mm, "_mmap", None)
        if base is not None:
            base.close()
    except Exception:
        pass


def _init_worker(feature_path: str, metric: str, block_rows: int, device: str) -> None:
    global _W_FEATURES, _W_METRIC, _W_BLOCK_ROWS, _W_XP
    _W_FEATURES = np.load(feature_path, mmap_mode="r")
    _W_METRIC = metric
    _W_BLOCK_ROWS = max(32, int(block_rows))
    if device == "gpu":
        import cupy as cp  # noqa: F401 - imported for its side effect / availability

        _W_XP = cp
    else:
        _W_XP = np


def _chunk_worker(task: tuple[int, int, int, int, int]) -> dict:
    """Upper-triangle distances for query rows [r0, r1) against all j > i.

    Returns the raw distances (row-major, i ascending then j ascending), a local
    top-K heap of the smallest, the chunk max, and the pair count.
    """
    chunk_idx, r0, r1, n, keep_top = task
    feats = _W_FEATURES
    if feats is None:
        raise RuntimeError("streaming worker not initialised")
    xp = _W_XP
    on_gpu = xp is not np

    count = sum((n - 1 - i) for i in range(r0, r1))
    out = np.empty(count, dtype=np.float32)
    local_heap: list[tuple[float, int, int]] = []
    dmax = 0.0
    idx = 0

    for i in range(r0, r1):
        j0 = i + 1
        if j0 >= n:
            continue
        q = feats[i]
        if on_gpu:
            q = xp.asarray(q)
        row = np.empty(n - j0, dtype=np.float64)
        for b0 in range(j0, n, _W_BLOCK_ROWS):
            b1 = min(n, b0 + _W_BLOCK_ROWS)
            blk = feats[b0:b1]
            if on_gpu:
                blk = xp.asarray(blk)
            d = _distance_kernel(blk, q, _W_METRIC, xp)
            row[b0 - j0:b1 - j0] = xp.asnumpy(d) if on_gpu else d
        if row.size:
            m = float(row.max())
            if m > dmax:
                dmax = m
        out[idx:idx + row.size] = row
        for off, dval in enumerate(row):
            j = j0 + off
            d = float(dval)
            if len(local_heap) < keep_top:
                heapq.heappush(local_heap, (-d, i, j))
            elif d < -local_heap[0][0]:
                heapq.heapreplace(local_heap, (-d, i, j))
        idx += row.size

    return {"chunk_idx": chunk_idx, "start": r0, "end": r1,
            "count": count, "raw": out, "top_heap": local_heap, "dmax": dmax}


# --------------------------------------------------------------------------- #
# Stats from the raw memmap (exact moments; sampled quantiles for huge N)
# --------------------------------------------------------------------------- #
_PCTS = [1, 5, 10, 25, 50, 75, 90, 95, 99]


def stats_and_sample_from_memmap(
    raw: np.memmap, *, sample_cap: int = 1_000_000
) -> tuple[dict, np.ndarray]:
    """Exact min/max/mean/std over the whole memmap; percentiles + plot sample
    from a uniform stride (exact when the data already fits under *sample_cap*)."""
    total = int(raw.shape[0])
    if total == 0:
        return {"count": 0}, np.empty(0, dtype=np.float32)

    # Exact moments via a blocked pass (never loads the whole array at once).
    dmin, dmax = np.inf, -np.inf
    s = 0.0
    ss = 0.0
    block = 4_000_000
    for b0 in range(0, total, block):
        chunk = np.asarray(raw[b0:b0 + block], dtype=np.float64)
        dmin = min(dmin, float(chunk.min()))
        dmax = max(dmax, float(chunk.max()))
        s += float(chunk.sum())
        ss += float((chunk * chunk).sum())
    mean = s / total
    var = max(0.0, ss / total - mean * mean)

    step = max(1, total // sample_cap)
    # np.array (not asarray) forces a copy so the sample survives closing the memmap.
    sample = np.array(raw[::step], dtype=np.float32)
    pct_vals = np.percentile(sample, _PCTS).astype(float)

    stats = {
        "count": total,
        "min_distance": dmin,
        "max_distance": dmax,
        "mean_distance": mean,
        "std_dev": var ** 0.5,
        "median_distance": float(pct_vals[_PCTS.index(50)]),
        "percentiles": {p: float(v) for p, v in zip(_PCTS, pct_vals)},
        "percentiles_sampled": step > 1,
    }
    return stats, sample


def expected_unique_pairs(n: int, seg_start: int = 0, seg_end: int | None = None) -> int:
    seg_end = n if seg_end is None else seg_end
    return int(sum((n - 1 - i) for i in range(seg_start, seg_end)))


# --------------------------------------------------------------------------- #
# The streaming driver
# --------------------------------------------------------------------------- #
def pairwise_topk_stream(
    feature_path: str,
    n: int,
    metric: str,
    *,
    seg_start: int = 0,
    seg_end: int | None = None,
    workers: int = 6,
    chunk_rows: int = 64,
    keep_top: int = 4096,
    block_rows: int = 384,
    device: str = "cpu",
    raw_memmap_path: str | None = None,
    sample_cap: int = 1_000_000,
    progress: bool = True,
) -> dict:
    """Stream the upper-triangle sweep of a memmapped ``(n, D)`` feature file.

    *feature_path* must be an ``.npy`` written with ``np.save`` (workers mmap it
    read-only). Returns a dict with the raw-distance memmap path, exact stats, the
    global smallest-``keep_top`` unique pairs (distances + i/j indices), the global
    max distance, and a bounded plotting sample. The caller owns the memmap file
    and should delete it when finished.
    """
    if metric not in VALID_METRICS:
        raise ValueError(f"metric must be one of {VALID_METRICS}, got {metric!r}")
    seg_end = n if seg_end is None else seg_end
    total = expected_unique_pairs(n, seg_start, seg_end)
    workers = max(1, int(workers))
    chunk_rows = max(1, int(chunk_rows))

    if raw_memmap_path is None:
        tmp = tempfile.NamedTemporaryFile(prefix="indep_raw_", suffix=".dat", delete=False)
        raw_memmap_path = tmp.name
        tmp.close()
    raw = np.memmap(raw_memmap_path, dtype=np.float32, mode="w+", shape=(max(total, 1),))

    global_heap: list[tuple[float, int, int]] = []
    dmax = 0.0
    start = time.time()
    seg_rows = seg_end - seg_start

    def _merge_heap(items: Iterable[tuple[float, int, int]]) -> None:
        for neg_d, ii, jj in items:
            d = -float(neg_d)
            if len(global_heap) < keep_top:
                heapq.heappush(global_heap, (-d, int(ii), int(jj)))
            elif d < -global_heap[0][0]:
                heapq.heapreplace(global_heap, (-d, int(ii), int(jj)))

    def _progress(rows_done: int) -> None:
        if not progress:
            return
        elapsed = time.time() - start
        pairs_done = int((rows_done / max(1, seg_rows)) * total)
        rate = pairs_done / elapsed if elapsed > 0 else 0.0
        eta = (total - pairs_done) / rate if rate > 0 else 0.0
        sys.stdout.write(
            f"\r[COMPARE] [{_bar(rows_done, seg_rows)}] {rows_done}/{seg_rows} rows "
            f"({100.0 * rows_done / max(1, seg_rows):6.2f}%) | elapsed {_fmt(elapsed)} "
            f"| eta {_fmt(eta)} | {rate:10.0f} pair/s"
        )
        sys.stdout.flush()

    tasks = []
    chunk_idx = 0
    cursor = seg_start
    while cursor < seg_end:
        end = min(seg_end, cursor + chunk_rows)
        tasks.append((chunk_idx, cursor, end, n, keep_top))
        cursor = end
        chunk_idx += 1

    if workers == 1:
        global _W_FEATURES
        _init_worker(feature_path, metric, block_rows, device)
        write_idx = 0
        rows_done = 0
        try:
            for task in tasks:
                res = _chunk_worker(task)
                cvals = res["raw"]
                raw[write_idx:write_idx + cvals.shape[0]] = cvals
                write_idx += cvals.shape[0]
                _merge_heap(res["top_heap"])
                dmax = max(dmax, res["dmax"])
                rows_done += res["end"] - res["start"]
                _progress(rows_done)
        finally:
            # Release the feature memmap this process opened (Windows unlink safety).
            _close_memmap(_W_FEATURES)
            _W_FEATURES = None
    else:
        buffered: dict[int, dict] = {}
        pending = 0
        write_idx = 0
        rows_done = 0
        max_inflight = max(2 * workers, workers + 2)
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(feature_path, metric, block_rows, device),
        ) as ex:
            task_iter = iter(tasks)
            futures = set()
            for _ in range(min(max_inflight, len(tasks))):
                try:
                    futures.add(ex.submit(_chunk_worker, next(task_iter)))
                except StopIteration:
                    break
            last_beat = 0.0
            while futures:
                done_set, futures = concurrent.futures.wait(
                    futures, timeout=1.0,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                now = time.time()
                if not done_set:
                    if progress and now - last_beat >= 1.0:
                        _progress(rows_done)
                        last_beat = now
                    continue
                for fut in done_set:
                    res = fut.result()
                    buffered[res["chunk_idx"]] = res
                    dmax = max(dmax, res["dmax"])
                    while pending in buffered:
                        cur = buffered.pop(pending)
                        cvals = cur["raw"]
                        raw[write_idx:write_idx + cvals.shape[0]] = cvals
                        write_idx += cvals.shape[0]
                        _merge_heap(cur["top_heap"])
                        rows_done += cur["end"] - cur["start"]
                        pending += 1
                    try:
                        futures.add(ex.submit(_chunk_worker, next(task_iter)))
                    except StopIteration:
                        pass
                _progress(rows_done)
                last_beat = now
    if progress:
        sys.stdout.write("\n")
        sys.stdout.flush()

    raw.flush()
    stats, sample = stats_and_sample_from_memmap(raw, sample_cap=sample_cap)
    # Close the raw memmap so the caller can reopen or delete the file on Windows.
    _close_memmap(raw)
    del raw

    ordered = sorted(global_heap, key=lambda t: -t[0])  # ascending distance
    top_d = np.array([-t[0] for t in ordered], dtype=np.float64)
    top_i = np.array([t[1] for t in ordered], dtype=np.int64)
    top_j = np.array([t[2] for t in ordered], dtype=np.int64)

    return {
        "raw_memmap_path": raw_memmap_path,
        "unique_pairs": total,
        "ordered_comparisons": n * (n - 1),
        "stats": stats,
        "sample": sample,
        "top_distances": top_d,
        "top_i": top_i,
        "top_j": top_j,
        "max_distance": float(dmax),
    }
