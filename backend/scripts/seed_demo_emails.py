"""Seed the mailbox with demo messages and run the email agent over them.

Why this exists: the email agent normally gets its input from IMAP. For a demo
(or a first look at the feature) you often don't want to wire up a real mailbox,
so this inserts realistic messages directly and then calls the *real*
``/emails/{id}/retriage`` endpoint, so classification, retrieval, and drafting all
run through the same code path a live sync would use.

    # with the stack running (docker compose up)
    docker compose exec backend python scripts/seed_demo_emails.py

    # or locally, from backend/ with the app running on :8000
    python scripts/seed_demo_emails.py --api-url http://localhost:8000

Re-running is safe: messages already present (matched on Message-ID) are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from app.core.config import get_settings
from app.database.engine import build_engine, build_sessionmaker
from app.features.emails.models import Email, EmailStatus
from app.features.users.dependencies import WORKSPACE_USER_EMAIL
from app.features.users.models import User
from sqlalchemy import select

_NOW = datetime.now(UTC)

# Three messages chosen to show three different behaviours:
#   1. billing question  -> grounds on the billing policy PDF
#
# Note the invoice number and amount are deliberately NOT the ones used as the
# example inside the classifier prompt (INV-2231 / $420.00). If the model echoed
# its own example instead of reading the message, that would be indistinguishable
# from real extraction — using different values here makes it provable.
#   2. HR question       -> grounds on the employee handbook PDF
#   3. spam              -> classified, then deliberately NOT drafted
DEMO_EMAILS: list[dict[str, Any]] = [
    {
        "uid": "9001",
        "message_id": "<demo-invoice-4187@vendor.test>",
        "sender": "Amara Chen <a.chen@brightpath.test>",
        "subject": "Invoice INV-4187 — when will this be paid?",
        "received_at": _NOW - timedelta(hours=3),
        "body": (
            "Hi there,\n\n"
            "I'm following up on invoice INV-4187 for $1,860.00, dated 1 July. Our "
            "records show it as still outstanding and I wanted to check where it "
            "sits in your payment run.\n\n"
            "Could you confirm the payment terms you work to, and whether any late "
            "fee applies at this point? If it's easier to pay by card rather than "
            "bank transfer, let me know if that changes anything.\n\n"
            "Thanks,\nAmara Chen\nAccounts Receivable, BrightPath Ltd"
        ),
    },
    {
        "uid": "9002",
        "message_id": "<demo-leave-question@team.test>",
        "sender": "Tomas Oyelaran <t.oyelaran@northwind.test>",
        "subject": "Question about carrying over unused holiday",
        "received_at": _NOW - timedelta(hours=6),
        "body": (
            "Hello,\n\n"
            "I have 7 vacation days left this year and I won't be able to use all "
            "of them before December. Can I carry them into next year, and if so is "
            "there a deadline before they disappear?\n\n"
            "Also, I'm hoping to work from my family's place in Portugal for a few "
            "weeks in spring — is that allowed, and is there a limit?\n\n"
            "Thanks for your help,\nTomas"
        ),
    },
    {
        "uid": "9003",
        "message_id": "<demo-spam-seo@marketing.test>",
        "sender": "Growth Team <no-reply@rankboost-pro.test>",
        "subject": "🚀 FINAL NOTICE: Your website is INVISIBLE on Google!!",
        "received_at": _NOW - timedelta(hours=1),
        "body": (
            "Dear Website Owner,\n\n"
            "Our AUTOMATED SCAN found 47 CRITICAL SEO ERRORS on your website. You "
            "are LOSING customers every single day!!!\n\n"
            "For a LIMITED TIME we are offering our Platinum Growth Package at 90% "
            "OFF — normally $4,999, yours today for only $499!!\n\n"
            "Reply YES within 24 hours to claim this offer. Act now before your "
            "competitors do!\n\n"
            "Unsubscribe | Growth Team"
        ),
    },
]


async def seed(api_url: str) -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)

    inserted: list[tuple[str, str]] = []
    try:
        async with sessionmaker() as session:
            # The workspace identity owns everything (no accounts — see
            # docs/COMPLETION_PLAN.md §3). Provision it if this is a fresh database.
            user = (
                await session.execute(
                    select(User).where(User.email == WORKSPACE_USER_EMAIL)
                )
            ).scalar_one_or_none()
            if user is None:
                user = User(email=WORKSPACE_USER_EMAIL, is_active=True)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                print(f"provisioned workspace identity {user.email}")

            for payload in DEMO_EMAILS:
                existing = (
                    await session.execute(
                        select(Email).where(Email.message_id == payload["message_id"])
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    print(f"skip   {payload['subject'][:52]!r} (already seeded)")
                    continue

                mail = Email(
                    user_id=user.id,
                    status=EmailStatus.RECEIVED,
                    entities={},
                    **payload,
                )
                session.add(mail)
                await session.commit()
                await session.refresh(mail)
                inserted.append((str(mail.id), str(payload["subject"])))
                print(f"insert {payload['subject'][:52]!r}")
    finally:
        await engine.dispose()

    if not inserted:
        print("\nNothing new to triage.")
        return

    # Triage through the real endpoint so the agent, the recorder, and retrieval
    # all behave exactly as they would after a live IMAP sync.
    print(f"\nTriaging {len(inserted)} message(s) via {api_url} …")
    async with httpx.AsyncClient(timeout=300.0) as client:
        for email_id, subject in inserted:
            try:
                response = await client.post(
                    f"{api_url}/api/v1/emails/{email_id}/retriage"
                )
            except httpx.HTTPError as exc:
                print(f"  FAILED {subject[:44]!r}: API unreachable ({exc})")
                continue
            if response.status_code != 200:
                print(f"  FAILED {subject[:44]!r}: HTTP {response.status_code}")
                continue
            data = response.json()["data"]
            grounded = {True: "grounded", False: "ungrounded", None: "—"}[data["grounded"]]
            print(
                f"  {data['status']:<18} intent={data['intent']:<10} "
                f"{grounded:<10} {subject[:40]!r}"
            )

    print(
        "\nDone. Open the Email page — messages with a draft are under "
        "'Needs review'.\nThe spam message is classified and intentionally left "
        "undrafted."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the running backend (default: %(default)s)",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.api_url))


if __name__ == "__main__":
    main()
