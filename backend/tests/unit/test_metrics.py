"""Unit tests for the metrics registry and its Prometheus exposition."""

from __future__ import annotations

import pytest
from app.platform.metrics.registry import MetricsRegistry


@pytest.fixture
def registry() -> MetricsRegistry:
    return MetricsRegistry()


class TestCounter:
    def test_increments_and_renders(self, registry: MetricsRegistry) -> None:
        counter = registry.counter("things_total", "Things.")
        counter.inc()
        counter.inc(2)

        assert "things_total 3.0" in registry.render()

    def test_labels_produce_separate_series(self, registry: MetricsRegistry) -> None:
        counter = registry.counter("calls_total", "Calls.")
        counter.inc(provider="groq")
        counter.inc(provider="groq")
        counter.inc(provider="ollama")

        output = registry.render()

        assert 'calls_total{provider="groq"} 2.0' in output
        assert 'calls_total{provider="ollama"} 1.0' in output

    def test_label_order_does_not_split_a_series(
        self, registry: MetricsRegistry
    ) -> None:
        """Otherwise the same logical series would double-count depending on
        the order a caller happened to pass its kwargs."""
        counter = registry.counter("calls_total", "Calls.")
        counter.inc(provider="groq", outcome="ok")
        counter.inc(outcome="ok", provider="groq")

        assert registry.render().count("calls_total{") == 1
        assert "2.0" in registry.render()

    def test_an_unused_counter_still_emits_a_zero(
        self, registry: MetricsRegistry
    ) -> None:
        """A missing series and a zero series look very different on a graph."""
        registry.counter("quiet_total", "Nothing yet.")

        assert "quiet_total 0" in registry.render()

    def test_help_and_type_are_declared(self, registry: MetricsRegistry) -> None:
        registry.counter("things_total", "Things counted.")
        output = registry.render()

        assert "# HELP things_total Things counted." in output
        assert "# TYPE things_total counter" in output

    def test_quotes_in_a_label_are_escaped(self, registry: MetricsRegistry) -> None:
        """An unescaped quote produces a payload Prometheus cannot parse."""
        registry.counter("odd_total", "Odd.").inc(name='we"ird')

        assert 'name="we\\"ird"' in registry.render()

    def test_the_same_name_returns_the_same_counter(
        self, registry: MetricsRegistry
    ) -> None:
        registry.counter("shared_total", "Shared.").inc()
        registry.counter("shared_total", "Shared.").inc()

        assert "shared_total 2.0" in registry.render()


class TestHistogram:
    def test_buckets_are_cumulative(self, registry: MetricsRegistry) -> None:
        histogram = registry.histogram("latency_seconds", "Latency.", buckets=(1, 5))
        histogram.observe(0.5)
        histogram.observe(3.0)

        output = registry.render()

        assert 'latency_seconds_bucket{le="1"} 1' in output
        assert 'latency_seconds_bucket{le="5"} 2' in output

    def test_sum_and_count_are_reported(self, registry: MetricsRegistry) -> None:
        histogram = registry.histogram("latency_seconds", "Latency.", buckets=(1, 5))
        histogram.observe(1.0)
        histogram.observe(2.0)

        output = registry.render()

        assert "latency_seconds_sum 3.0" in output
        assert "latency_seconds_count 2" in output

    def test_an_inf_bucket_holds_everything(self, registry: MetricsRegistry) -> None:
        """Required by the format, and it is where over-budget outliers land."""
        histogram = registry.histogram("latency_seconds", "Latency.", buckets=(1,))
        histogram.observe(0.5)
        histogram.observe(900.0)

        output = registry.render()

        assert 'latency_seconds_bucket{le="1"} 1' in output
        assert 'latency_seconds_bucket{le="+Inf"} 2' in output

    def test_labels_partition_the_histogram(self, registry: MetricsRegistry) -> None:
        histogram = registry.histogram("latency_seconds", "Latency.", buckets=(1,))
        histogram.observe(0.5, route="/a")
        histogram.observe(0.5, route="/b")

        output = registry.render()

        assert 'latency_seconds_count{route="/a"} 1' in output
        assert 'latency_seconds_count{route="/b"} 1' in output

    def test_bucket_edges_render_without_float_noise(
        self, registry: MetricsRegistry
    ) -> None:
        registry.histogram("d_seconds", "D.", buckets=(0.005, 1.0)).observe(0.001)

        output = registry.render()

        assert 'le="0.005"' in output
        assert 'le="1"' in output


class TestExposition:
    def test_output_ends_with_a_newline(self, registry: MetricsRegistry) -> None:
        """Prometheus rejects a body whose final line is unterminated."""
        registry.counter("a_total", "A.").inc()

        assert registry.render().endswith("\n")

    def test_metrics_are_ordered_deterministically(
        self, registry: MetricsRegistry
    ) -> None:
        registry.counter("z_total", "Z.").inc()
        registry.counter("a_total", "A.").inc()

        output = registry.render()

        assert output.index("a_total") < output.index("z_total")
