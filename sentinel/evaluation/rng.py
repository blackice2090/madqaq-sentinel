"""Version-stable deterministic randomness.

Only ``Random.random()`` (Mersenne Twister, identical across CPython versions) is used;
every other helper is built on it, so generated benchmarks and bootstrap intervals do
not depend on the Python version's ``randint``/``choice``/``shuffle`` implementations.
"""
from __future__ import annotations

import hashlib
import random
from typing import Sequence, TypeVar

T = TypeVar("T")


class StableRandom:
    def __init__(self, *key: object):
        material = "|".join(str(k) for k in key).encode("utf-8")
        self._rng = random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], "big"))

    def random(self) -> float:
        return self._rng.random()

    def randint(self, low: int, high: int) -> int:
        """Uniform integer in [low, high] (inclusive)."""
        if high < low:
            raise ValueError("high must be >= low")
        return low + int(self._rng.random() * (high - low + 1))

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self.randint(0, len(seq) - 1)]

    def chance(self, probability: float) -> bool:
        return self._rng.random() < probability

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.randint(0, i)
            items[i], items[j] = items[j], items[i]
