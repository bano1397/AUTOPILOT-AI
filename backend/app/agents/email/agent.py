"""The email agent: classify → extract → retrieve → draft.

Reuses the pieces already in place rather than adding a parallel stack: the
recorder audits both LLM calls, `RagService` supplies grounding, and the drafted
reply is persisted for a human to send. **Nothing is ever sent by this agent** —
the send is a separate, explicit human action (see
``app/features/emails/service.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.agents.email.parsing import ClassifiedEmail, parse_classification
from app.agents.email.prompts import build_classify_messages, build_draft_messages
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProvider
from app.features.rag.service import RagService
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import register_agent

logger = get_logger("app.agents.email")

# How much company knowledge to ground a reply in.
_DRAFT_TOP_K = 4


@dataclass(frozen=True)
class EmailDraftOutcome:
    """What the agent decided about one message."""

    classification: ClassifiedEmail
    draft: str | None
    grounded: bool
    model: str


# Not supervisor_routable: this agent is driven by the email triage pipeline
# (sync -> classify -> draft), not by the supervisor graph, so a workflow
# version must not be able to route chat messages to it.
@register_agent(name="email")
class EmailAgent:
    """Triages one inbound message and drafts a grounded reply."""

    name = "email"
    description = "Classifies inbound email, extracts entities, and drafts a reply."

    def __init__(
        self,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
        rag: RagService,
    ) -> None:
        self._llm = llm
        self._recorder = recorder
        self._rag = rag

    async def triage(
        self, user_id: UUID, *, sender: str, subject: str, body: str
    ) -> EmailDraftOutcome:
        """Classify the message, then draft a reply unless it is spam."""
        classify_result = await self._recorder.chat(
            self._llm,
            build_classify_messages(sender, subject, body),
            feature="email.classify",
            agent_name=self.name,
            user_id=user_id,
            temperature=0.0,
            prompt_key="agent.email.classify",
            prompt_version=1,
        )
        classification = parse_classification(classify_result.content)

        # Spam gets classified and stopped: drafting a reply to it would waste
        # tokens and risk engaging with an attacker.
        if classification.intent.value == "spam":
            return EmailDraftOutcome(
                classification=classification,
                draft=None,
                grounded=False,
                model=classify_result.model,
            )

        query = f"{subject}\n{body[:1000]}".strip()
        try:
            matches = await self._rag.query(user_id, query, top_k=_DRAFT_TOP_K)
        except Exception as exc:  # noqa: BLE001 - degrade to an ungrounded draft
            logger.warning("email.retrieval_failed", extra={"error": str(exc)})
            matches = []

        draft_result = await self._recorder.chat(
            self._llm,
            build_draft_messages(
                sender, subject, body, classification.intent.value, matches
            ),
            feature="email.draft",
            agent_name=self.name,
            user_id=user_id,
            temperature=0.3,
            prompt_key="agent.email.draft",
            prompt_version=1,
        )
        return EmailDraftOutcome(
            classification=classification,
            draft=draft_result.content.strip(),
            grounded=bool(matches),
            model=draft_result.model,
        )
