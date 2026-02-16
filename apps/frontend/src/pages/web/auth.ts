const WEB_AUTH_KEY = "tb_web_user";
const WEB_SESSION_KEY = "tb_web_session_token";
const WEB_PORTAL_ID_KEY = "tb_web_portal_id";
const WEB_PORTAL_TOKEN_KEY = "tb_web_portal_token";

export type WebUser = {
  email: string;
  company?: string;
  createdAt: string;
};

export function getWebUser(): WebUser | null {
  const raw = localStorage.getItem(WEB_AUTH_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as WebUser;
  } catch {
    return null;
  }
}

export function setWebUser(user: WebUser) {
  localStorage.setItem(WEB_AUTH_KEY, JSON.stringify(user));
}

export function setWebSession(sessionToken: string, portalId: number, portalToken: string) {
  localStorage.setItem(WEB_SESSION_KEY, sessionToken);
  localStorage.setItem(WEB_PORTAL_ID_KEY, String(portalId));
  localStorage.setItem(WEB_PORTAL_TOKEN_KEY, portalToken);
}

export function updateWebPortalInfo(portalId: number, portalToken: string) {
  localStorage.setItem(WEB_PORTAL_ID_KEY, String(portalId));
  localStorage.setItem(WEB_PORTAL_TOKEN_KEY, portalToken);
}

export function getWebSessionToken(): string | null {
  return localStorage.getItem(WEB_SESSION_KEY);
}

export function getWebPortalInfo() {
  const portalId = Number(localStorage.getItem(WEB_PORTAL_ID_KEY) || 0);
  const portalToken = localStorage.getItem(WEB_PORTAL_TOKEN_KEY) || "";
  return { portalId, portalToken };
}

export async function refreshWebPortalToken(): Promise<string | null> {
  const sessionToken = getWebSessionToken();
  if (!sessionToken) return null;
  try {
    const res = await fetch("/api/v1/web/auth/me", {
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        Accept: "application/json",
      },
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.portal_token || !data?.portal_id) return null;
    updateWebPortalInfo(Number(data.portal_id), String(data.portal_token));
    return String(data.portal_token);
  } catch {
    return null;
  }
}

export async function fetchPortal(url: string, init: RequestInit = {}) {
  const { portalToken } = getWebPortalInfo();
  const headers = {
    Authorization: `Bearer ${portalToken}`,
    "X-Requested-With": "XMLHttpRequest",
    Accept: "application/json",
    ...(init.headers || {}),
  } as Record<string, string>;
  let res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    const refreshed = await refreshWebPortalToken();
    if (refreshed) {
      const retryHeaders = { ...headers, Authorization: `Bearer ${refreshed}` };
      res = await fetch(url, { ...init, headers: retryHeaders });
    }
  }
  return res;
}

export async function fetchWeb(url: string, init: RequestInit = {}) {
  const sessionToken = getWebSessionToken();
  const headers = {
    ...(init.headers || {}),
    Accept: "application/json",
  } as Record<string, string>;
  if (sessionToken) {
    headers.Authorization = `Bearer ${sessionToken}`;
  }
  return fetch(url, { ...init, headers });
}

export function clearWebUser() {
  localStorage.removeItem(WEB_AUTH_KEY);
  localStorage.removeItem(WEB_SESSION_KEY);
  localStorage.removeItem(WEB_PORTAL_ID_KEY);
  localStorage.removeItem(WEB_PORTAL_TOKEN_KEY);
}
