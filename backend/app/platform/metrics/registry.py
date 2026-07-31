"""A minimal Prometheus-compatible metrics registry.

Hand-rolled rather than pulling in ``prometheus-client``, for the same reason
the HTTP providers here speak their APIs directly: the exposition format is a
few lines of text, and this needs counters and histograms with labels — not a
multiprocess-aware collector framework.

**In-process and per-replica.** Counters reset when the process restarts and
each replica reports only its own traffic. That is exactly what Prometheus
expects (it scrapes each instance and aggregates), but it does mean these
numbers are not a substitute for the ``ai_executions`` table, which is durable
and is what the cost dashboard reads.

Scraping never touches the database. A ``/metrics`` endpoint that ran queries
would add load in proportion to how closely it is watched, which is backwards.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass, field

# Seconds. Chosen around what this platform actually does: sub-100ms CRUD at
# the bottom, and LLM calls that routinely take seconds at the top.
DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005, 0.025, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0,
)

Labels = tuple[tuple[str, str], ...]


def _label_key(labels: dict[str, str] | None) -> Labels:
    """Normalise labels into a hashable, order-independent key."""
    return tuple(sorted((labels or {}).items()))


def _render_labels(labels: Labels, extra: tuple[str, str] | None = None) -> str:
    pairs = list(labels)
    if extra:
        pairs.append(extra)
    if not pairs:
        return ""
    inner = ",".join(f'{name}="{_escape(value)}"' for name, value in pairs)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


@dataclass
class Counter:
    """A monotonically increasing value."""

    name: str
    help_text: str
    values: dict[Labels, float] = field(default_factory=dict)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = _label_key(labels)
        self.values[key] = self.values.get(key, 0.0) + amount

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        if not self.values:
            # Emit a zero sample so the series exists before the first event;
            # a missing series and a zero series look very different on a graph.
            lines.append(f"{self.name} 0")
        for labels, value in sorted(self.values.items()):
            lines.append(f"{self.name}{_render_labels(labels)} {value}")
        return lines


@dataclass
class Histogram:
    """Cumulative buckets, a sum, and a count — the Prometheus shape."""

    name: str
    help_text: str
    buckets: tuple[float, ...] = DEFAULT_BUCKETS
    counts: dict[Labels, list[int]] = field(default_factory=dict)
    sums: dict[Labels, float] = field(default_factory=dict)
    totals: dict[Labels, int] = field(default_factory=dict)

    def observe(self, value: float, **labels: str) -> None:
        key = _label_key(labels)
        if key not in self.counts:
            self.counts[key] = [0] * len(self.buckets)
        for index, edge in enumerate(self.buckets):
            if value <= edge:
                self.counts[key][index] += 1
        self.sums[key] = self.sums.get(key, 0.0) + value
        self.totals[key] = self.totals.get(key, 0) + 1

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} histogram",
        ]
        for labels in sorted(self.counts):
            cumulative = 0
            for index, edge in enumerate(self.buckets):
                # Buckets are cumulative: le="0.1" counts everything at or
                # under 0.1, not only what fell in that band.
                cumulative = self.counts[labels][index]
                lines.append(
                    f"{self.name}_bucket"
                    f"{_render_labels(labels, ('le', _format_edge(edge)))} {cumulative}"
                )
            lines.append(
                f"{self.name}_bucket{_render_labels(labels, ('le', '+Inf'))} "
                f"{self.totals[labels]}"
            )
            lines.append(f"{self.name}_sum{_render_labels(labels)} {self.sums[labels]}")
            lines.append(
                f"{self.name}_count{_render_labels(labels)} {self.totals[labels]}"
            )
        return lines


def _format_edge(edge: float) -> str:
    """Render a bucket edge the way Prometheus does (no trailing .0 noise)."""
    return f"{edge:g}"


class MetricsRegistry:
    """The process's metrics, and their exposition."""

    def __init__(self) -> None:
        # Metric mutation happens from the event loop, but a threaded worker
        # (extraction, OCR, SMTP) could record too; the lock keeps a dict
        # resize from racing a scrape.
        self._lock = threading.Lock()
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}

    def counter(self, name: str, help_text: str) -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name=name, help_text=help_text)
            return self._counters[name]

    def histogram(
        self,
        name: str,
        help_text: str,
        buckets: Sequence[float] = DEFAULT_BUCKETS,
    ) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(
                    name=name, help_text=help_text, buckets=tuple(buckets)
                )
            return self._histograms[name]

    def render(self) -> str:
        """The full exposition, in Prometheus text format v0.0.4."""
        with self._lock:
            lines: list[str] = []
            for counter in sorted(self._counters.values(), key=lambda c: c.name):
                lines.extend(counter.render())
            for histogram in sorted(self._histograms.values(), key=lambda h: h.name):
                lines.extend(histogram.render())
        return "\n".join(lines) + "\n"

    def clear(self) -> None:
        """Drop everything (tests only)."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()


# Process-wide singleton, mirroring how the prompt and plugin registries work.
metrics = MetricsRegistry()
