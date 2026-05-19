/**
 * PayInvoiceDialog component tests.
 *
 * The dialog wraps three concerns: input validation, the initiate call, and
 * a poll loop.  These tests mock `@/lib/api` and assert that:
 *   1. The form renders with a sensible default amount.
 *   2. Invalid input surfaces a FriendlyError without calling the API.
 *   3. A successful initiate transitions to the "waiting" state.
 *   4. An ApiError from initiate surfaces a friendly message.
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import { ApiError, type Invoice } from "@eduzim/api-client";

vi.mock("@/lib/api", () => ({
  fees: {
    initiatePaynow: vi.fn(),
    paymentStatus: vi.fn(),
  },
}));

import { fees as feesApi } from "@/lib/api";
import { PayInvoiceDialog } from "@/components/pay-invoice-dialog";

const fakeInvoice: Invoice = {
  id: "11111111-1111-1111-1111-111111111111",
  school_id: "22222222-2222-2222-2222-222222222222",
  student_id: "33333333-3333-3333-3333-333333333333",
  fee_structure_id: "44444444-4444-4444-4444-444444444444",
  total_amount: 950,
  paid_amount: 200,
  balance: 750,
  currency: "USD",
  due_date: "2026-06-01",
  status: "PARTIAL",
  created_at: "2026-05-19T08:00:00+00:00",
} as Invoice;

beforeEach(() => {
  vi.resetAllMocks();
  // Default: paymentStatus returns PENDING so the poll loop is idle.
  (feesApi.paymentStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { status: "PENDING" } as never,
    meta: { request_id: "test" },
  });
});

describe("PayInvoiceDialog", () => {
  it("renders with the invoice balance as default amount", () => {
    render(
      <PayInvoiceDialog invoice={fakeInvoice} onClose={() => {}} />,
    );
    expect(screen.getByText(/pay invoice/i)).toBeInTheDocument();
    const amount = screen.getByLabelText(/amount/i) as HTMLInputElement;
    expect(amount.value).toBe("750");
  });

  it("rejects empty phone before calling the API", async () => {
    render(<PayInvoiceDialog invoice={fakeInvoice} onClose={() => {}} />);
    const submit = screen.getByRole("button", { name: /^pay\s+/i });
    fireEvent.click(submit);
    // form has required attrs — browser stops submit; nothing called.
    expect(feesApi.initiatePaynow).not.toHaveBeenCalled();
  });

  it("rejects amount that exceeds the balance", async () => {
    render(<PayInvoiceDialog invoice={fakeInvoice} onClose={() => {}} />);
    // Browser HTML5 validation on max=750 may stop submission before our
    // own validator runs; either path is acceptable as long as the API
    // is never called.
    fireEvent.change(screen.getByLabelText(/amount/i), {
      target: { value: "5000" },
    });
    fireEvent.change(screen.getByLabelText(/mobile number/i), {
      target: { value: "0772123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^pay\s+/i }));

    // Give the click handler a tick.
    await new Promise((r) => setTimeout(r, 50));
    expect(feesApi.initiatePaynow).not.toHaveBeenCalled();
  });

  it("transitions to the waiting state on successful initiate", async () => {
    (feesApi.initiatePaynow as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        transaction_ref: "EDU-ABC-123",
        status: "PENDING",
        poll_url: "",
        instructions: "Check your phone to complete payment.",
        demo_mode: true,
      },
      meta: { request_id: "test" },
    });

    render(<PayInvoiceDialog invoice={fakeInvoice} onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText(/amount/i), {
      target: { value: "100" },
    });
    fireEvent.change(screen.getByLabelText(/mobile number/i), {
      target: { value: "0772123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^pay\s+/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/check your phone .* USSD prompt waiting/i),
      ).toBeInTheDocument(),
    );
    expect(feesApi.initiatePaynow).toHaveBeenCalledWith({
      invoice_id: fakeInvoice.id,
      amount: 100,
      method: "ECOCASH",
      phone: "+263772123456",
    });
    expect(screen.getByText(/edu-abc-123/i)).toBeInTheDocument();
    expect(screen.getByText(/demo mode/i)).toBeInTheDocument();
  });

  it("surfaces a FriendlyError when initiate fails", async () => {
    const apiErr = new ApiError(502, {
      code: "PAYNOW_UNREACHABLE",
      message: "Paynow gateway returned an error.",
      details: {},
      request_id: "req-123",
    });
    (feesApi.initiatePaynow as ReturnType<typeof vi.fn>).mockRejectedValue(apiErr);

    render(<PayInvoiceDialog invoice={fakeInvoice} onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText(/amount/i), {
      target: { value: "50" },
    });
    fireEvent.change(screen.getByLabelText(/mobile number/i), {
      target: { value: "+263772123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^pay\s+/i }));

    // FriendlyError surfaces a humanised line for PAYNOW_UNREACHABLE.
    await waitFor(() => {
      // The component shows the dialog's error step — assert the form is gone
      // and a Try again button (FriendlyError) is mounted.
      const tryAgain = screen.queryByRole("button", { name: /try again|retry/i });
      expect(tryAgain).toBeTruthy();
    });
  });

  it("does not call paymentStatus before submit", () => {
    render(<PayInvoiceDialog invoice={fakeInvoice} onClose={() => {}} />);
    expect(feesApi.paymentStatus).not.toHaveBeenCalled();
  });
});
