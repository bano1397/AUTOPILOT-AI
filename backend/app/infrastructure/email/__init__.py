"""Email infrastructure: IMAP reading and SMTP sending."""

from app.infrastructure.email.imap import ImapEmailReader, SmtpEmailSender

__all__ = ["ImapEmailReader", "SmtpEmailSender"]
