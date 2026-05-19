/**
 * Friendly error catalog
 * =======================
 * Maps machine error codes to human-friendly Title + Body + Suggested Fix.
 * Keep entries SHORT and ACTIONABLE. Teachers and parents read these on a
 * 5" phone screen with poor signal — they need to know "what do I do now?"
 * within 3 seconds.
 *
 * Codes follow the convention: <DOMAIN>_<REASON>
 *   NET_OFFLINE              browser sees offline
 *   NET_TIMEOUT              request timed out
 *   AUTH_EXPIRED             token expired
 *   AUTH_INVALID             bad credentials
 *   PERM_DENIED              403 / RBAC failure
 *   PAYNOW_UNREACHABLE       Paynow API not responding
 *   PAYNOW_INVALID_HASH      signature mismatch
 *   SMS_PROVIDER_DOWN        Africa's Talking unreachable
 *   WHATSAPP_NOT_OPTED_IN    parent hasn't accepted templates
 *   ATTENDANCE_SYNC_FAILED   queued attendance couldn't flush
 *   VALIDATION_FAILED        422 from a service
 *   UPSTREAM_5XX             generic downstream failure
 *   UNKNOWN                  fallback
 *
 * The frontend never displays the raw code; only `title` + `body` + `fix`.
 * Technical details (status code, request_id, raw message) live behind a
 * "Show technical details" disclosure for support tickets.
 */

export type FriendlyErrorCode =
  | "NET_OFFLINE"
  | "NET_TIMEOUT"
  | "AUTH_EXPIRED"
  | "AUTH_INVALID"
  | "PERM_DENIED"
  | "PAYNOW_UNREACHABLE"
  | "PAYNOW_INVALID_HASH"
  | "SMS_PROVIDER_DOWN"
  | "EMAIL_PROVIDER_DOWN"
  | "PUSH_PROVIDER_DOWN"
  | "WHATSAPP_NOT_OPTED_IN"
  | "WHATSAPP_NOT_CONFIGURED"
  | "NOTIFICATION_WORKER_STALLED"
  | "ATTENDANCE_SYNC_FAILED"
  | "VALIDATION_FAILED"
  | "INVALID_STATE"
  | "NOT_FOUND"
  | "UPSTREAM_5XX"
  | "UNKNOWN";

export interface FriendlyErrorEntry {
  /** One-line headline, max ~60 chars. */
  title: string;
  /** Plain-language explanation, max ~140 chars. */
  body: string;
  /** Next action the user should try. */
  fix: string;
  /** Whether retry is likely to succeed without user changing anything. */
  retryable: boolean;
}

export const ERROR_CATALOG: Record<FriendlyErrorCode, FriendlyErrorEntry> = {
  NET_OFFLINE: {
    title: "You're offline right now",
    body: "We saved your work on this device. It will send automatically when the internet comes back.",
    fix: "Check your data or Wi-Fi. The app keeps working — just keep going.",
    retryable: true,
  },
  NET_TIMEOUT: {
    title: "The connection is slow",
    body: "Your phone reached us but the answer is taking too long.",
    fix: "Wait 10 seconds, then tap Retry. Move to a spot with better signal if you can.",
    retryable: true,
  },
  AUTH_EXPIRED: {
    title: "Please sign in again",
    body: "For your safety we sign you out after a while.",
    fix: "Tap Sign In and use the same email and PIN as before.",
    retryable: false,
  },
  AUTH_INVALID: {
    title: "Wrong email or password",
    body: "We couldn't find an account with those details.",
    fix: "Check spelling. If you forgot, tap 'Forgot password' on the sign-in page.",
    retryable: false,
  },
  PERM_DENIED: {
    title: "You can't do this yet",
    body: "Your role doesn't include this action.",
    fix: "Ask your school administrator to give you permission.",
    retryable: false,
  },
  PAYNOW_UNREACHABLE: {
    title: "Paynow isn't responding",
    body: "Zimbabwe's payment service is temporarily unavailable.",
    fix: "Wait a few minutes and try again. Your invoice is safe.",
    retryable: true,
  },
  PAYNOW_INVALID_HASH: {
    title: "Payment couldn't be verified",
    body: "Paynow sent a confirmation but it doesn't match our records.",
    fix: "Don't worry — no money was taken. Contact your school office and quote the invoice number.",
    retryable: false,
  },
  SMS_PROVIDER_DOWN: {
    title: "Text messages aren't sending",
    body: "Our SMS partner is having problems.",
    fix: "We'll keep trying in the background. You don't need to do anything.",
    retryable: true,
  },
  EMAIL_PROVIDER_DOWN: {
    title: "Emails aren't going out",
    body: "Our email server isn't reachable right now.",
    fix: "We'll retry automatically. Check email server settings if this lasts more than an hour.",
    retryable: true,
  },
  PUSH_PROVIDER_DOWN: {
    title: "Push notifications are stuck",
    body: "Firebase isn't responding from this server.",
    fix: "Other channels still work. Check the FCM key on the Integrations page.",
    retryable: true,
  },
  WHATSAPP_NOT_OPTED_IN: {
    title: "Parent hasn't joined WhatsApp updates",
    body: "We can only send WhatsApp messages to parents who agreed.",
    fix: "Ask the parent to reply YES to the welcome message, or send by SMS instead.",
    retryable: false,
  },
  WHATSAPP_NOT_CONFIGURED: {
    title: "WhatsApp isn't connected yet",
    body: "This school hasn't linked its WhatsApp Business account.",
    fix: "Ask an administrator to add the WhatsApp keys on the Integrations page.",
    retryable: false,
  },
  NOTIFICATION_WORKER_STALLED: {
    title: "Notifications are piling up",
    body: "The background worker hasn't sent messages in a while.",
    fix: "Open the Integrations page and run the messaging test. Restart the worker if it stays red.",
    retryable: true,
  },
  ATTENDANCE_SYNC_FAILED: {
    title: "Attendance is waiting to send",
    body: "Your marks are saved on this device. They will go through when you're back online.",
    fix: "Keep marking. The app will sync everything as soon as it can.",
    retryable: true,
  },
  VALIDATION_FAILED: {
    title: "Some details need fixing",
    body: "One or more fields aren't quite right.",
    fix: "Check the highlighted fields for missing or unusual entries.",
    retryable: false,
  },
  INVALID_STATE: {
    title: "That action isn't allowed right now",
    body: "The item is in a state that doesn't accept this change.",
    fix: "Refresh the page to see the current status, then try again.",
    retryable: false,
  },
  NOT_FOUND: {
    title: "We couldn't find that item",
    body: "It may have been deleted or you might be looking at an old link.",
    fix: "Go back and reload the list.",
    retryable: false,
  },
  UPSTREAM_5XX: {
    title: "Something went wrong on our side",
    body: "Our system had a hiccup. This isn't your fault.",
    fix: "Tap Retry. If it keeps happening, tell your school administrator.",
    retryable: true,
  },
  UNKNOWN: {
    title: "Something unexpected happened",
    body: "We couldn't recognise this problem.",
    fix: "Tap Retry. If you keep seeing this, share the technical details with support.",
    retryable: true,
  },
};

/**
 * Best-effort mapping from an error thrown by the api-client to a code.
 * `err` may be:
 *   - ApiError-like with a numeric `status`
 *   - Error with .message
 *   - Anything else
 */
export function classifyError(err: unknown): FriendlyErrorCode {
  if (!err) return "UNKNOWN";
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return "NET_OFFLINE";
  }

  const e = err as { status?: number; code?: string; message?: string };
  if (e.code && (ERROR_CATALOG as Record<string, unknown>)[e.code]) {
    return e.code as FriendlyErrorCode;
  }

  const msg = (e.message || "").toLowerCase();
  if (msg.includes("timeout") || msg.includes("network")) return "NET_TIMEOUT";

  switch (e.status) {
    case 401:
      return msg.includes("expired") ? "AUTH_EXPIRED" : "AUTH_INVALID";
    case 403:
      return "PERM_DENIED";
    case 422:
      return "VALIDATION_FAILED";
    case 502:
    case 503:
    case 504:
      return "UPSTREAM_5XX";
    default:
      if (e.status && e.status >= 500) return "UPSTREAM_5XX";
      return "UNKNOWN";
  }
}
