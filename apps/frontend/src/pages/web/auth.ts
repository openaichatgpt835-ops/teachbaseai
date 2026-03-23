const WEB_AUTH_KEY = "tb_web_user";
const WEB_SESSION_KEY = "tb_web_session_token";
const WEB_PORTAL_ID_KEY = "tb_web_portal_id";
const WEB_PORTAL_TOKEN_KEY = "tb_web_portal_token";
const WEB_ACTIVE_ACCOUNT_ID_KEY = "tb_web_active_account_id";
const WEB_ACCOUNTS_KEY = "tb_web_accounts";

export type WebUser = {
  email: string;
  company?: string;
  createdAt: string;
};

export type WebAccount = {
  id: number;
  account_no?: number | null;
  name?: string | null;
  slug?: string | null;
  role?: string | null;
  status?: string | null;
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

export function getWebAccounts(): WebAccount[] {
  const raw = localStorage.getItem(WEB_ACCOUNTS_KEY);
  if (!raw) return [];
  try {
    const items = JSON.parse(raw) as WebAccount[];
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

export function setWebAccounts(accounts: WebAccount[]) {
  localStorage.setItem(WEB_ACCOUNTS_KEY, JSON.stringify(accounts || []));
}

export function getActiveAccountId(): number {
  return Number(localStorage.getItem(WEB_ACTIVE_ACCOUNT_ID_KEY) || 0);
}

export function setActiveAccountId(accountId: number | null | undefined) {
  if (accountId && Number.isFinite(accountId) && accountId > 0) {
    localStorage.setItem(WEB_ACTIVE_ACCOUNT_ID_KEY, String(accountId));
  } else {
    localStorage.removeItem(WEB_ACTIVE_ACCOUNT_ID_KEY);
  }
}

export function setWebSession(
  sessionToken: string,
  portalId: number,
  portalToken: string,
  activeAccountId?: number | null,
  accounts?: WebAccount[] | null,
) {
  localStorage.setItem(WEB_SESSION_KEY, sessionToken);
  localStorage.setItem(WEB_PORTAL_ID_KEY, String(portalId));
  localStorage.setItem(WEB_PORTAL_TOKEN_KEY, portalToken);
  setActiveAccountId(activeAccountId || null);
  if (accounts) {
    setWebAccounts(accounts);
  }
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
    setActiveAccountId(Number(data?.active_account_id || 0) || null);
    if (Array.isArray(data?.accounts)) {
      setWebAccounts(data.accounts);
    }
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
  localStorage.removeItem(WEB_ACTIVE_ACCOUNT_ID_KEY);
  localStorage.removeItem(WEB_ACCOUNTS_KEY);
}

export async function switchWebAccount(accountId: number): Promise<boolean> {
  const sessionToken = getWebSessionToken();
  if (!sessionToken || !accountId) return false;
  try {
    const res = await fetch("/api/v1/web/auth/switch-account", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ account_id: accountId }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.portal_id || !data?.portal_token) return false;
    setWebSession(
      String(data.session_token || sessionToken),
      Number(data.portal_id),
      String(data.portal_token),
      Number(data?.active_account_id || accountId),
      Array.isArray(data?.accounts) ? data.accounts : null,
    );
    return true;
  } catch {
    return false;
  }
}
