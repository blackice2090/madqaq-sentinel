"""Engine-evaluation latency (M4.1).

Scope: the time a system takes to evaluate evidence that ALREADY exists as domain
events. It excludes camera capture, YOLO detection, tracking, event construction and UI
rendering, so it is NOT end-to-end latency, and it is specific to the machine that ran it.
"""
from __future__ import annotations

import gc
import math
import os
import platform
import sys
from time import perf_counter_ns

from sentinel.evaluation.adapters import EvaluatedSystem, Evidence


def percentile(sorted_values: list[int], q: float) -> int:
    """Nearest-rank percentile (q in (0, 100]) of an ascending list."""
    if not sorted_values:
        raise ValueError("no samples")
    rank = max(1, math.ceil(q / 100.0 * len(sorted_values)))
    return sorted_values[rank - 1]


def environment_info() -> dict:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "timer": "time.perf_counter_ns",
    }


def measure_latency(system: EvaluatedSystem, evidences: list[Evidence], *, warmup: int = 100, repeats: int = 5) -> dict:
    """Median / P95 / P99 of per-evaluation wall time in microseconds, after a warm-up."""
    if not evidences:
        raise ValueError("no evidence to measure")
    for i in range(warmup):                       # warm-up: results discarded
        system.evaluate(evidences[i % len(evidences)])
    samples: list[int] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            for ev in evidences:
                t0 = perf_counter_ns()
                system.evaluate(ev)
                samples.append(perf_counter_ns() - t0)
    finally:
        if gc_was_enabled:
            gc.enable()
    samples.sort()
    us = lambda ns: round(ns / 1000.0, 3)
    return {
        "samples": len(samples),
        "warmup_evaluations": warmup,
        "median_us": us(percentile(samples, 50)),
        "p95_us": us(percentile(samples, 95)),
        "p99_us": us(percentile(samples, 99)),
        "mean_us": us(sum(samples) // len(samples)),
        "min_us": us(samples[0]),
        "max_us": us(samples[-1]),
    }
