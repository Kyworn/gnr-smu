#!/usr/bin/env python3
"""Offline analysis of a vermeer_transient.py run (local machine).

Usage: python3 research/vermeer_track.py /path/to/run.jsonl

Outputs:
  1. per-phase medians (k10temp, RAPL power, PM candidates)
  2. Tctl ranking: Pearson/Spearman/RMSE/MAE/offset/gain per d[i],
     plus a +-2 s lag search for the top candidates
  3. package-power check: RAPL package/core power vs d[1] and mirrors,
     per phase and per workload type
Needs numpy only.
"""
import json
import sys

import numpy as np

PHASE_ORDER = ["idle", "matrix-1", "cooldown", "matrix-3", "cooldown",
               "matrix-12", "cooldown", "int64-6", "cooldown", "cache-6",
               "cooldown"]


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "pm" in obj:
                rows.append(obj)
    t0 = rows[0]["t"]
    for r in rows:
        r["dt"] = r["t"] - t0
    return rows


def pearson(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def ranks(v):
    v = np.asarray(v, float)
    order = np.argsort(v, kind="mergesort")
    r = np.empty(len(v))
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def affine(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    a, b = np.polyfit(x, y, 1)
    pred = a * x + b
    return (float(a), float(b), float(np.sqrt(np.mean((y - pred) ** 2))),
            float(np.mean(np.abs(y - pred))))


def phase_median(rows, phase, fn):
    vals = [fn(r) for r in rows if r["phase"] == phase]
    return float(np.median(vals)) if vals else float("nan")


def rapl_power(rows, key="package-0"):
    """Per-sample RAPL power (W); wraps/negative diffs become NaN."""
    t = np.array([r["dt"] for r in rows])
    e = np.array([r["rapl"].get(key, float("nan")) for r in rows], float)
    p = np.full(len(rows), float("nan"))
    dt = np.diff(t)
    de = np.diff(e)
    ok = (dt > 0) & (de >= 0)
    p[1:][ok] = de[ok] / 1e6 / dt[ok]
    return p


def main():
    rows = load(sys.argv[1])
    print(f"samples: {len(rows)}, span {rows[-1]['dt']:.1f} s")
    tctl = np.array([r["k10"].get("Tctl", float("nan")) for r in rows])
    pm = np.array([r["pm"] for r in rows])
    print("== 1. per-phase medians ==")
    print(f"{'phase':10} {'Tctl':>7} {'Tccd1':>7} {'RAPLpkg':>8} "
          f"{'d1':>7} {'d13':>7} {'d29':>7} {'d150':>7} "
          f"{'d127':>7} {'d140':>7} {'d144':>7} {'d145':>7} {'d358':>7}")
    phases = []
    for r in rows:
        if r["phase"] not in phases:
            phases.append(r["phase"])
    rp = rapl_power(rows)
    for i, r in enumerate(rows):
        r["_rpkg"] = rp[i]
    for ph in phases:
        g = lambda f, ph=ph: phase_median(rows, ph, f)  # noqa: E731
        print(f"{ph:10} {g(lambda r: r['k10'].get('Tctl', float('nan'))):7.2f} "
              f"{g(lambda r: r['k10'].get('Tccd1', float('nan'))):7.2f} "
              f"{g(lambda r: r['_rpkg']):8.2f} "
              + " ".join(f"{g(lambda r, i=i: r['pm'][i]):7.2f}"
                         for i in (1, 13, 29, 150, 127, 140, 144, 145, 358)))

    print("== 2. Tctl ranking (all samples) ==")
    dyn = [i for i in range(pm.shape[1]) if np.std(pm[:, i]) > 1e-9]
    scored = []
    for i in dyn:
        y = pm[:, i]
        try:
            pr, sp = pearson(tctl, y), spearman(tctl, y)
        except Exception:
            continue
        if np.isnan(pr):
            continue
        a, b, rmse, mae = affine(tctl, y)
        scored.append((abs(pr), pr, sp, i, a, b, rmse, mae,
                       float(np.mean(y))))
    scored.sort(reverse=True)
    print(f"{'d':>4} {'pearson':>8} {'spearman':>8} {'gain':>8} "
          f"{'offset':>8} {'rmse':>7} {'mae':>7} {'mean':>8}")
    for _, pr, sp, i, a, b, rmse, mae, mean in scored[:30]:
        print(f"{i:4d} {pr:+8.4f} {sp:+8.4f} {a:+8.4f} {b:+8.3f} "
              f"{rmse:7.3f} {mae:7.3f} {mean:8.3f}")

    print("== 3. lag search for top candidates (shift PM by s, Pearson) ==")
    top = [s[3] for s in scored[:8]]
    t = np.array([r["dt"] for r in rows])
    for i in top:
        y = pm[:, i]
        best = (0.0, -2.0)
        for lag in np.arange(-2.0, 2.01, 0.2):
            # shift PM forward by lag: compare tctl(t) with pm(t - lag)
            yi = np.interp(t - lag, t, y)
            pr = pearson(tctl, yi)
            if not np.isnan(pr) and abs(pr) > abs(best[0]):
                best = (pr, round(float(lag), 1))
        print(f"d[{i}]: best Pearson {best[0]:+.4f} at lag {best[1]:+.1f} s")

    print("== 4. package power: RAPL vs candidates per phase ==")
    cands = {"d1": 1, "d13": 13, "d29": 29, "d150": 150,
             "corePsum": None, "d3": 3, "d9": 9, "d15": 15, "d24": 24}
    print(f"{'phase':10} {'RAPLpkg':>8} {'RAPLcore':>8} " +
          " ".join(f"{k:>8}" for k in cands))
    rc = rapl_power(rows, "core")
    for i, r in enumerate(rows):
        r["_rcore"] = rc[i]
    for ph in phases:
        sub = [r for r in rows if r["phase"] == ph]
        rp_med = float(np.nanmedian([r["_rpkg"] for r in sub]))
        rc_med = float(np.nanmedian([r["_rcore"] for r in sub]))
        cells = []
        for k, idx in cands.items():
            if idx is None:
                v = float(np.median(
                    [r["pm"][172 + s] for r in sub
                     for s in (0, 1, 4, 5, 6, 7)]))
            else:
                v = float(np.median([r["pm"][idx] for r in sub]))
            cells.append(f"{v:8.2f}")
        print(f"{ph:10} {rp_med:8.2f} {rc_med:8.2f} " + " ".join(cells))
    # overall RAPLpkg vs d1 Pearson (steady-state: last 60% of each phase)
    steady = []
    for ph in phases:
        sub = [r for r in rows if r["phase"] == ph]
        steady += sub[int(len(sub) * 0.4):]
    x = np.array([r["_rpkg"] for r in steady])
    ok = ~np.isnan(x)
    for k, idx in (("d1", 1), ("d150", 150), ("corePsum", None)):
        if idx is None:
            y = np.array([sum(r["pm"][172 + s] for s in (0, 1, 4, 5, 6, 7))
                          for r in steady])
        else:
            y = np.array([r["pm"][idx] for r in steady])
        m = ok & ~np.isnan(y)
        a, b, rmse, mae = affine(x[m], y[m])
        print(f"RAPLpkg vs {k}: Pearson {pearson(x[m], y[m]):+.4f}, "
              f"gain {a:+.3f}, offset {b:+.2f}, RMSE {rmse:.2f}, MAE {mae:.2f}")


if __name__ == "__main__":
    main()
