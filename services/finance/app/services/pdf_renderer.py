"""
Tiny pure-Python PDF writer — single-page, multi-line text only.

Why not reportlab/fpdf?  Our invoice + receipt PDFs are short, text-only,
mostly tabular.  A 120-line pure-Python emitter avoids dragging an extra
~10MB native dependency into every fees-service container while keeping our
tests dependency-free.

If we ever need logos / barcodes / multi-page tables, swap this out for
reportlab — the public surface is just :func:`build_invoice_pdf` and
:func:`build_receipt_pdf`, both of which return ``bytes``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


# ─────────────── Low-level PDF emitter ───────────────

PAGE_WIDTH = 612    # 8.5"
PAGE_HEIGHT = 792   # 11"
MARGIN_X = 54       # ~0.75"
START_Y = 740
LINE_H = 16


def _escape_pdf(text: str) -> str:
    """Escape `()` and `\\` for PDF literal strings."""
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _content_stream(lines: Iterable[tuple[str, int, int]]) -> bytes:
    """Each line is ``(text, font_size, indent_x)``."""
    ops: list[str] = ["BT"]
    y = START_Y
    first = True
    for text, size, indent in lines:
        x = MARGIN_X + indent
        if first:
            ops.append(f"/F1 {size} Tf")
            ops.append(f"{x} {y} Td")
            first = False
        else:
            ops.append(f"/F1 {size} Tf")
            # Move relative to the previous origin: PDF Td is relative.
            ops.append(f"0 -{LINE_H} Td")
        ops.append(f"({_escape_pdf(text)}) Tj")
        y -= LINE_H
    ops.append("ET")
    return "\n".join(ops).encode("latin-1", errors="replace")


def _make_pdf(lines: list[tuple[str, int, int]]) -> bytes:
    content = _content_stream(lines)

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 " + f"{PAGE_WIDTH} {PAGE_HEIGHT}".encode()
            + b"] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
        + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(b"trailer\n")
    out.extend(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode())
    out.extend(f"startxref\n{xref_pos}\n%%EOF".encode())
    return bytes(out)


# ─────────────── Business-facing renderers ───────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def build_invoice_pdf(
    *,
    invoice: dict,
    school_name: str = "EduZim School",
    student_name: str | None = None,
    line_items: list[dict] | None = None,
) -> bytes:
    """Render an invoice PDF.

    ``line_items`` is ``[{label, amount}]``; if absent we render a single
    line with the invoice total.
    """
    cur = invoice.get("currency", "USD")
    lines: list[tuple[str, int, int]] = [
        (school_name, 18, 0),
        ("Tax Invoice", 13, 0),
        ("", 10, 0),
        (f"Invoice ID: {invoice.get('id', '')}", 10, 0),
        (f"Issued:     {_now()}", 10, 0),
        (f"Due date:   {invoice.get('due_date', '')}", 10, 0),
        (f"Status:     {invoice.get('status', '')}", 10, 0),
        ("", 10, 0),
        ("Bill to:", 11, 0),
        (f"  Student ID: {invoice.get('student_id', '')}", 10, 0),
    ]
    if student_name:
        lines.append((f"  Name:       {student_name}", 10, 0))
    lines.append(("", 10, 0))
    lines.append(("Line items", 12, 0))
    lines.append(("-" * 60, 10, 0))

    if not line_items:
        line_items = [{"label": "School fees", "amount": invoice.get("total_amount", 0.0)}]

    for it in line_items:
        label = (it.get("label") or "")[:40]
        amt = _fmt_money(float(it.get("amount", 0.0)), cur)
        lines.append((f"{label:<42}{amt:>18}", 10, 0))

    lines.append(("-" * 60, 10, 0))
    lines.append((f"{'Total':<42}{_fmt_money(invoice.get('total_amount', 0.0), cur):>18}", 11, 0))
    lines.append((f"{'Paid':<42}{_fmt_money(invoice.get('paid_amount', 0.0), cur):>18}", 11, 0))
    lines.append((f"{'Balance':<42}{_fmt_money(invoice.get('balance', 0.0), cur):>18}", 12, 0))
    lines.append(("", 10, 0))
    lines.append(("Pay via EcoCash, OneMoney, Mukuru, or Telecash through your", 9, 0))
    lines.append(("EduZim parent portal. Reference this invoice ID on payment.", 9, 0))

    return _make_pdf(lines)


def build_receipt_pdf(
    *,
    payment: dict,
    invoice: dict,
    school_name: str = "EduZim School",
    student_name: str | None = None,
) -> bytes:
    cur = payment.get("currency", invoice.get("currency", "USD"))
    lines: list[tuple[str, int, int]] = [
        (school_name, 18, 0),
        ("Payment Receipt", 13, 0),
        ("", 10, 0),
        (f"Receipt ID:   {payment.get('id', '')}", 10, 0),
        (f"Issued:       {_now()}", 10, 0),
        (f"Paid at:      {payment.get('paid_at') or payment.get('created_at', '')}", 10, 0),
        (f"Method:       {payment.get('method', '')}", 10, 0),
        (f"Reference:    {payment.get('reference', '')}", 10, 0),
        ("", 10, 0),
        ("Applied to invoice:", 11, 0),
        (f"  Invoice ID:   {invoice.get('id', '')}", 10, 0),
        (f"  Student ID:   {invoice.get('student_id', '')}", 10, 0),
    ]
    if student_name:
        lines.append((f"  Student name: {student_name}", 10, 0))
    lines.append(("", 10, 0))
    lines.append(("-" * 60, 10, 0))
    lines.append((f"{'Amount paid':<42}{_fmt_money(payment.get('amount', 0.0), cur):>18}", 12, 0))
    lines.append((f"{'Invoice total':<42}{_fmt_money(invoice.get('total_amount', 0.0), cur):>18}", 10, 0))
    lines.append((f"{'Invoice paid':<42}{_fmt_money(invoice.get('paid_amount', 0.0), cur):>18}", 10, 0))
    lines.append((f"{'Remaining balance':<42}{_fmt_money(invoice.get('balance', 0.0), cur):>18}", 11, 0))
    lines.append(("-" * 60, 10, 0))
    lines.append(("", 10, 0))
    lines.append(("Thank you. Keep this receipt for your records.", 9, 0))
    return _make_pdf(lines)
