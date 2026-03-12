/**
 * EduZim Auth — Token Store
 * ===========================
 * Access token in memory only.
 * Refresh token lives in an httpOnly cookie managed by the gateway.
 */

export interface TokenInfo {
  accessToken: string;
  expiresAt: number; // Unix ms
}

let _token: TokenInfo | null = null;

export function setTokens(access: string, expiresIn: number) {
  _token = {
    accessToken: access,
    expiresAt: Date.now() + expiresIn * 1000,
  };
}

export function getAccessToken(): string | null {
  if (!_token) return null;
  if (Date.now() >= _token.expiresAt) return null; // expired
  return _token.accessToken;
}

export function clearTokens() {
  _token = null;
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}
