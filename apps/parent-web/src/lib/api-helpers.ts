/**
 * Thin fetch helpers for the parent-web Phase 12 pages.
 *
 * The api-client package doesn't yet have typed wrappers for every
 * Phase 12 backend route (the surface is large and most pages are
 * one-shot fetches), so we use direct fetch with bearer auth. When
 * the api-client gains typed coverage in a follow-up, the calls
 * here become drop-in replacements.
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";


async function authHeader(): Promise<Record<string, string>> {
  const { getAccessToken } = await import("@eduzim/auth");
  const tok = getAccessToken();
  return tok ? { Authorization: `Bearer ${tok}` } : {};
}


export async function fetchJson<T>(path: string): Promise<{ data: T }> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: await authHeader(),
  });
  if (!res.ok) {
    throw new Error(`fetch ${path} failed: ${res.status}`);
  }
  return res.json();
}


export async function postJson(
  path: string, body: unknown,
): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await authHeader()) },
    body: JSON.stringify(body),
  });
}


export async function putJson(
  path: string, body: unknown,
): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: { "content-type": "application/json", ...(await authHeader()) },
    body: JSON.stringify(body),
  });
}


export async function downloadFile(path: string, filename: string) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: await authHeader(),
  });
  if (!res.ok) throw new Error(`download ${path} failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
