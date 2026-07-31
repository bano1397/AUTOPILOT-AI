"""The metrics this platform actually records.

Defined in one place rather than scattered across call sites, so the metric
names, labels, and help text stay consistent — and so it is obvious at a glance
what is instrumented.

Label cardinality is the thing to be careful with: a label whose values are
unbounded (a run id, a user's question) multiplies the series count until the
scrape becomes the expensive part. Everything labelled here is drawn from a
small fixed set — route templates, provider names, statuses.
"""

from __future__ import annotations

from app.platform.metrics.registry import metrics

# --- HTTP -------------------------------------------------------------------

_http_requests = metrics.counter(
    "autopilot_http_requests_total",
    "HTTP requests handled, by method, route template, and status class.",
)
_http_duration = metrics.histogram(
    "autopilot_http_request_duration_seconds",
    "HTTP request latency, by method and route template.",
)

# --- AI ---------------------------------------------------------------------

_ai_calls = metrics.counter(
    "autopilot_ai_calls_total",
    "LLM calls, by provider, feature, and outcome.",
)
_ai_tokens = metrics.counter(
    "autopilot_ai_tokens_total",
    "Tokens consumed, by provider and direction (prompt/completion).",
)
_ai_duration = metrics.histogram(
    "autopilot_ai_call_duration_seconds",
    "LLM call latency, by provider.",
)

# --- Workflows --------------------------------------------------------------

_workflow_runs = metrics.counter(
    "autopilot_workflow_runs_total",
    "Workflow runs, by workflow name and terminal status.",
)


def observe_http_request(
    *, method: str, route: str, status_code: int, duration_seconds: float
) -> None:
    """Record one handled request.

    ``route`` must be the *template* (``/api/v1/documents/{document_id}``), not
    the resolved path: one series per document id would be unbounded.
    """
    _http_requests.inc(
        method=method, route=route, status=f"{status_code // 100}xx"
    )
    _http_duration.observe(duration_seconds, method=method, route=route)


def observe_ai_call(
    *,
    provider: str,
    feature: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_seconds: float,
    error: bool,
) -> None:
    """Record one LLM call, successful or not."""
    _ai_calls.inc(
        provider=provider, feature=feature, outcome="error" if error else "ok"
    )
    if prompt_tokens:
        _ai_tokens.inc(prompt_tokens, provider=provider, direction="prompt")
    if completion_tokens:
        _ai_tokens.inc(completion_tokens, provider=provider, direction="completion")
    _ai_duration.observe(duration_seconds, provider=provider)


def observe_workflow_run(*, workflow: str, status: str) -> None:
    """Record a workflow run reaching a terminal state."""
    _workflow_runs.inc(workflow=workflow, status=status)
