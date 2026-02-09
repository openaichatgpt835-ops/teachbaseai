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

export function getWebSessionToken(): string | null {
  return localStorage.getItem(WEB_SESSION_KEY);
}

export function getWebPortalInfo() {
  const portalId = Number(localStorage.getItem(WEB_PORTAL_ID_KEY) || 0);
  const portalToken = localStorage.getItem(WEB_PORTAL_TOKEN_KEY) || "";
  return { portalId, portalToken };
}

export function clearWebUser() {
  localStorage.removeItem(WEB_AUTH_KEY);
  localStorage.removeItem(WEB_SESSION_KEY);
  localStorage.removeItem(WEB_PORTAL_ID_KEY);
  localStorage.removeItem(WEB_PORTAL_TOKEN_KEY);
}
