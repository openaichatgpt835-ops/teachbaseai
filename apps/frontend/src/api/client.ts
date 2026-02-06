const API_BASE = import.meta.env.VITE_API_BASE || "/api";

let token: string | null = null;

export function setAuthToken(t: string) {
  token = t;
  localStorage.setItem("admin_token", t);
}

export function getAuthToken(): string | null {
  if (!token) token = localStorage.getItem("admin_token");
  return token;
}

export function clearAuthToken() {
  token = null;
  localStorage.removeItem("admin_token");
}

async function fetchApi(path: string, init?: RequestInit) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) || {}),
  };
  const t = getAuthToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    clearAuthToken();
    window.location.href = "/admin/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return res.json();
}

export const api = {
  get: (path: string) => fetchApi(path),
  post: (path: string, body?: unknown) =>
    fetchApi(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: (path: string, body?: unknown) =>
    fetchApi(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: (path: string, body?: unknown) =>
    fetchApi(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};
