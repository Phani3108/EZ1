"""Phase 15a — Invite templates.

Small registry. Returns (subject, body) per (role, channel) pair.
Bodies are deliberately short — SMS-friendly. Email bodies can be
longer.

Substitution variables:
  * {school_name}
  * {full_name}
  * {invite_url}   — magic-link form
  * {manual_code}  — 6-digit fallback code

The dispatcher fills these from the InviteOutbox row + caller-supplied
context.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RenderedTemplate:
    subject: str
    body: str


# Per-channel character limits we try to respect for SMS / WhatsApp.
SMS_BODY_BUDGET = 160
WHATSAPP_BODY_BUDGET = 1000


def render(role: str, channel: str, ctx: dict) -> RenderedTemplate:
    """Render the invitation body for one (role, channel) pair.

    `ctx` must include: school_name, full_name, invite_url,
    manual_code. Missing keys are tolerated (rendered as empty
    string) — the message will still go out, just terser.
    """
    school = ctx.get("school_name", "your school")
    name = ctx.get("full_name", "there")
    url = ctx.get("invite_url", "")
    code = ctx.get("manual_code", "")

    if channel == "sms":
        if role == "Parent":
            body = (
                f"EduZim: Hi {name}. {school} has added your child. "
                f"Activate: {url} (or code {code})"
            )
        elif role == "Teacher":
            body = (
                f"EduZim: Hi {name}. {school} has added you as a teacher. "
                f"Activate: {url} (or code {code})"
            )
        elif role == "SchoolAdmin":
            body = (
                f"EduZim: Hi {name}. You're invited to administer {school}. "
                f"Activate: {url} (or code {code})"
            )
        else:
            body = (
                f"EduZim: Hi {name}. Activate your {school} account: "
                f"{url} (or code {code})"
            )
        return RenderedTemplate(subject="", body=body[:SMS_BODY_BUDGET])

    if channel == "whatsapp":
        if role == "Parent":
            body = (
                f"Hi {name} 👋\n\n"
                f"{school} has set up your EduZim parent account so you "
                f"can see your child's attendance, marks, and fees.\n\n"
                f"Tap to activate: {url}\n\n"
                f"Or use the manual code: *{code}*\n\n"
                f"— Powered by EduZim"
            )
        elif role == "Teacher":
            body = (
                f"Hi {name} 👋\n\n"
                f"{school} has set up your EduZim teacher account. "
                f"You'll see your classes and roster after activating.\n\n"
                f"Tap to activate: {url}\n\n"
                f"Or use the manual code: *{code}*"
            )
        elif role == "SchoolAdmin":
            body = (
                f"Hi {name} 👋\n\n"
                f"You're invited to administer {school} on EduZim.\n\n"
                f"Tap to activate: {url}\n\n"
                f"Or use the manual code: *{code}*"
            )
        else:
            body = (
                f"Hi {name} 👋\n\n"
                f"Activate your {school} EduZim account: {url}\n"
                f"Or use the manual code: *{code}*"
            )
        return RenderedTemplate(subject="", body=body[:WHATSAPP_BODY_BUDGET])

    if channel == "email":
        subject = f"Welcome to EduZim — finish setting up your {school} account"
        if role == "Parent":
            body = (
                f"Hi {name},\n\n"
                f"{school} has set up an EduZim parent account for you. "
                f"It will show you each child's attendance, marks, fees, "
                f"and communications from the school.\n\n"
                f"To activate, click the link below and set your password:\n\n"
                f"    {url}\n\n"
                f"If the link doesn't work, you can also activate by "
                f"entering this code in the app:\n\n"
                f"    {code}\n\n"
                f"This invitation will expire in 14 days.\n\n"
                f"Welcome aboard,\n"
                f"The {school} team"
            )
        elif role == "Teacher":
            body = (
                f"Hi {name},\n\n"
                f"{school} has set up an EduZim teacher account for you. "
                f"You'll see your classes, roster, and gradebook after "
                f"activating.\n\n"
                f"To activate, click the link below and set your password:\n\n"
                f"    {url}\n\n"
                f"Or enter this code in the app:\n\n"
                f"    {code}\n\n"
                f"This invitation will expire in 14 days.\n\n"
                f"Welcome aboard,\n"
                f"The {school} team"
            )
        elif role == "SchoolAdmin":
            body = (
                f"Hi {name},\n\n"
                f"You're invited to administer {school} on EduZim. "
                f"This gives you the school setup wizard, staff and "
                f"student records, and Ministry reporting tools.\n\n"
                f"To activate, click the link below and set your password:\n\n"
                f"    {url}\n\n"
                f"Or enter this code:\n\n"
                f"    {code}\n\n"
                f"This invitation will expire in 14 days."
            )
        else:
            body = (
                f"Hi {name},\n\n"
                f"Activate your {school} EduZim account:\n\n"
                f"    {url}\n\nOr enter this code: {code}\n"
            )
        return RenderedTemplate(subject=subject, body=body)

    # manual mode — admin reads body out loud or types it onto paper.
    subject = f"Activation details for {name}"
    body = (
        f"Manual activation for {name} ({role}).\n"
        f"School: {school}\n"
        f"Code: {code}\n"
        f"URL (if they have a phone with browser): {url}\n"
    )
    return RenderedTemplate(subject=subject, body=body)
