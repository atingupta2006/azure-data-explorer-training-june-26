"""Build shuffled event-type sequences that match locked lab counts."""

from __future__ import annotations

import random
from typing import TypeVar

T = TypeVar("T")


def expand_event_types(counts: dict[str, int], seed: int) -> list[str]:
    """Return a shuffled list of event types with exact per-type counts."""
    sequence: list[str] = []
    for event_type, n in counts.items():
        if n < 0:
            raise ValueError(f"negative count for {event_type}: {n}")
        sequence.extend([event_type] * n)
    expected = sum(counts.values())
    if len(sequence) != expected:
        raise ValueError(f"sequence length {len(sequence)} != sum(counts) {expected}")
    rng = random.Random(seed)
    rng.shuffle(sequence)
    return sequence


def pick_template(templates: list[T], event_type: str, index: int, key) -> T:
    """Pick a template row matching event_type (cycles when multiple match)."""
    matches = [t for t in templates if key(t) == event_type]
    if not matches:
        raise KeyError(f"no template for event type {event_type!r}")
    return matches[index % len(matches)]
