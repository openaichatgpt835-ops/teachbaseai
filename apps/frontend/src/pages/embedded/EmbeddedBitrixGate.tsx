import { useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router-dom";
import { formatRuntimeError } from "../../../../shared/ui/runtimeErrors";
import { setActiveAccountId, setWebSession, setWebUser, updateWebPortalInfo } from "../web/auth";

type EmbeddedBitrixContext = {
  portalId: number;
  portalDomain: string;
  isPortalAdmin: boolean;
  demoUntil: string | null;
  accountId: number | null;
  accountName: string | null;
  accountNo: number | null;
};

type BitrixAuthData = {
  access_token?: string;
  domain?: string;
  member_id?: string;
  user_id?: number | string;
  USER_ID?: number | string;
};

type BitrixAttachableAccount = {
  account_id: number;
  account_no?: number | null;
  name: string;
  role: string;
  attach_allowed: boolean;
  reason?: string | null;
  bitrix_portals_used: number;
  bitrix_portals_limit: number;
};

type BitrixLinkPrecheck = {
  status: string;
  email: string;
  portal_id: number;
  portal_domain?: string | null;
  same_portal_linked: boolean;
  can_create_new_account: boolean;
  attachable_accounts: BitrixAttachableAccount[];
  recommended_action: string;
};

declare global {
  interface Window {
    B24Js?: {
      initializeB24Frame?: () => Promise<{
        auth?: {
          getAuthData?: () => BitrixAuthData | null;
        };
      } | null>;
    };
  }
}

const LABELS = {
  loading: "\u0418\u043d\u0438\u0446\u0438\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f Bitrix24...",
  noAuth: "\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 Bitrix24. \u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0438\u0437 \u043f\u043e\u0440\u0442\u0430\u043b\u0430.",
  sessionFailed: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u043d\u044f\u0442\u044c embedded-\u0441\u0435\u0441\u0441\u0438\u044e.",
  login: "\u0412\u0445\u043e\u0434",
  register: "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f",
  email: "Email",
  password: "\u041f\u0430\u0440\u043e\u043b\u044c",
  company: "\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430",
  confirmRequired: "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 email. \u041f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u043c\u043e\u0436\u043d\u043e \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u043f\u0440\u0438\u0432\u044f\u0437\u043a\u0443.",
  attachTitle: "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443",
  attachSubtitle:
    "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435: \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0438\u043b\u0438 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u0442\u0435\u043a\u0443\u0449\u0438\u0439 Bitrix24 \u043a \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u043c\u0443 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f.",
  createAccount: "\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442",
  attachExisting: "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043a \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u043c\u0443",
  enter: "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c",
  openCabinet: "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043a\u0430\u0431\u0438\u043d\u0435\u0442",
  createHint:
    "\u041d\u043e\u0432\u044b\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0431\u0443\u0434\u0435\u0442 \u0441\u043e\u0437\u0434\u0430\u043d, \u0430 \u0442\u0435\u043a\u0443\u0449\u0438\u0439 Bitrix24 \u0441\u0442\u0430\u043d\u0435\u0442 \u0435\u0433\u043e \u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u0435\u0439.",
  notAdmin:
    "\u0414\u043b\u044f \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u044f \u043d\u0443\u0436\u043d\u044b \u043f\u0440\u0430\u0432\u0430 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0430 \u043f\u043e\u0440\u0442\u0430\u043b\u0430 Bitrix24.",
  linked: "\u041f\u0440\u0438\u0432\u044f\u0437\u043a\u0430 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0430. \u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043c \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441...",
  missingCredentials: "\u0423\u043a\u0430\u0436\u0438\u0442\u0435 email \u0438 \u043f\u0430\u0440\u043e\u043b\u044c.",
  authFailed: "\u041e\u0448\u0438\u0431\u043a\u0430 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0438\u0438.",
  registerFailed: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044e.",
  createFailed: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442.",
  attachFailed: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043f\u043e\u0440\u0442\u0430\u043b.",
  upgradeOrCreate:
    "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u043c\u0443 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e: \u043d\u0435 \u0445\u0432\u0430\u0442\u0430\u0435\u0442 \u043f\u0440\u0430\u0432 \u0438\u043b\u0438 \u0434\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442 \u043b\u0438\u043c\u0438\u0442 Bitrix24-\u043f\u043e\u0440\u0442\u0430\u043b\u043e\u0432.",
  attachUnavailable: "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e.",
  role: "\u0420\u043e\u043b\u044c",
  portals: "Bitrix24-\u043f\u043e\u0440\u0442\u0430\u043b\u044b",
} as const;

const BASE = "";

async function jsonRequest(url: string, init: RequestInit = {}) {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.headers || {}),
    },
  });
  const data = await response.json().catch(() => null);
  return { ok: response.ok, status: response.status, data };
}

export function EmbeddedBitrixGate() {
  const [statusMessage, setStatusMessage] = useState<string>(LABELS.loading);
  const [errorMessage, setErrorMessage] = useState("");
  const [ready, setReady] = useState(false);
  const [portalId, setPortalId] = useState(0);
  const [portalToken, setPortalToken] = useState("");
  const [portalDomain, setPortalDomain] = useState("");
  const [isPortalAdmin, setIsPortalAdmin] = useState(false);
  const [demoUntil, setDemoUntil] = useState<string | null>(null);
  const [accountId, setAccountIdState] = useState<number | null>(null);
  const [accountName, setAccountName] = useState<string | null>(null);
  const [accountNo, setAccountNo] = useState<number | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [company, setCompany] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [hint, setHint] = useState("");
  const [precheck, setPrecheck] = useState<BitrixLinkPrecheck | null>(null);

  const embeddedContext = useMemo<EmbeddedBitrixContext>(
    () => ({
      portalId,
      portalDomain,
      isPortalAdmin,
      demoUntil,
      accountId,
      accountName,
      accountNo,
    }),
    [portalId, portalDomain, isPortalAdmin, demoUntil, accountId, accountName, accountNo],
  );

  const syncLinkedStatus = async (nextPortalId: number, nextPortalToken: string, nextPortalDomain: string) => {
    const result = await jsonRequest(`${BASE}/api/v1/bitrix/portals/${nextPortalId}/web/status`, {
      headers: {
        Authorization: `Bearer ${nextPortalToken}`,
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    if (!result.ok) {
      throw new Error(formatRuntimeError(result.data?.detail || result.data?.error || "http_error", LABELS.sessionFailed));
    }
    setPortalDomain(String(result.data?.portal_domain || nextPortalDomain || ""));
    setDemoUntil(result.data?.demo_until || null);
    const nextAccountId = Number(result.data?.account_id || 0) || null;
    const nextAccountNo = Number(result.data?.account_no || 0) || null;
    setActiveAccountId(nextAccountId);
    setAccountIdState(nextAccountId);
    setAccountName(result.data?.account_name || null);
    setAccountNo(nextAccountNo);
    if (result.data?.linked) {
      const sessionResult = await jsonRequest(`${BASE}/api/v1/bitrix/portals/${nextPortalId}/web/embedded-session`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${nextPortalToken}`,
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      if (!sessionResult.ok || !sessionResult.data?.session_token) {
        throw new Error(formatRuntimeError(sessionResult.data?.detail || sessionResult.data?.error || "http_error", LABELS.sessionFailed));
      }
      setWebSession(
        String(sessionResult.data.session_token),
        Number(sessionResult.data.portal_id || nextPortalId),
        String(sessionResult.data.portal_token || nextPortalToken),
        Number(sessionResult.data.active_account_id || nextAccountId || 0) || null,
        Array.isArray(sessionResult.data.accounts) ? sessionResult.data.accounts : [],
      );
      setWebUser({
        email: String(sessionResult.data.email || result.data?.email || ""),
        createdAt: new Date().toISOString(),
      });
      setHint("");
      setPrecheck(null);
      setStatusMessage(LABELS.linked);
      setReady(true);
      return true;
    }
    setReady(false);
    return false;
  };

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        setStatusMessage(LABELS.loading);
        const b24 = window.B24Js?.initializeB24Frame ? await window.B24Js.initializeB24Frame() : null;
        const auth = b24?.auth?.getAuthData?.() || null;
        if (!auth) {
          if (!cancelled) {
            setErrorMessage(LABELS.noAuth);
            setStatusMessage("");
          }
          return;
        }
        const response = await jsonRequest(`${BASE}/api/v1/bitrix/session/start`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify({
            auth: {
              access_token: auth.access_token,
              domain: auth.domain,
              member_id: auth.member_id,
              user_id: auth.user_id ?? auth.USER_ID ?? null,
            },
          }),
        });
        if (!response.ok || !response.data?.portal_id || !response.data?.portal_token) {
          throw new Error(formatRuntimeError(response.data?.detail || response.data?.error || "http_error", LABELS.sessionFailed));
        }
        if (cancelled) return;
        const nextPortalId = Number(response.data.portal_id);
        const nextPortalToken = String(response.data.portal_token);
        const nextPortalDomain = String(auth.domain || "");
        updateWebPortalInfo(nextPortalId, nextPortalToken);
        setPortalId(nextPortalId);
        setPortalToken(nextPortalToken);
        setPortalDomain(nextPortalDomain);
        setIsPortalAdmin(Boolean(response.data?.is_portal_admin));
        if (!response.data?.is_portal_admin) {
          setErrorMessage(LABELS.notAdmin);
          setStatusMessage("");
          return;
        }
        const linked = await syncLinkedStatus(nextPortalId, nextPortalToken, nextPortalDomain);
        if (!linked && !cancelled) {
          setStatusMessage("");
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : LABELS.sessionFailed);
          setStatusMessage("");
        }
      }
    };
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = async () => {
    if (!portalId || !portalToken) return;
    if (!email.trim() || !password) {
      setErrorMessage(LABELS.missingCredentials);
      return;
    }
    setSubmitting(true);
    setErrorMessage("");
    setHint("");
    setPrecheck(null);
    try {
      if (authMode === "register") {
        const result = await jsonRequest(`${BASE}/api/v1/bitrix/portals/${portalId}/web/register`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${portalToken}`,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify({
            email: email.trim(),
            password,
            company: company.trim(),
          }),
        });
        if (!result.ok) {
          throw new Error(formatRuntimeError(result.data?.detail || result.data?.error || "http_error", LABELS.registerFailed));
        }
        setHint(LABELS.confirmRequired);
        return;
      }
      const result = await jsonRequest(`${BASE}/api/v1/bitrix/portals/${portalId}/web/link/precheck`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${portalToken}`,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });
      if (!result.ok) {
        throw new Error(formatRuntimeError(result.data?.detail || result.data?.error || "http_error", LABELS.authFailed));
      }
      const nextPrecheck = result.data as BitrixLinkPrecheck;
      if (nextPrecheck?.same_portal_linked || nextPrecheck?.recommended_action === "already_linked") {
        await syncLinkedStatus(portalId, portalToken, portalDomain);
        return;
      }
      setPrecheck(nextPrecheck);
      if (nextPrecheck?.recommended_action === "upgrade_or_create") {
        setHint(LABELS.upgradeOrCreate);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : LABELS.authFailed);
    } finally {
      setSubmitting(false);
    }
  };

  const createAccount = async () => {
    if (!portalId || !portalToken) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      const result = await jsonRequest(`${BASE}/api/v1/bitrix/portals/${portalId}/web/link/create-account`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${portalToken}`,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          account_name: company.trim() || portalDomain,
        }),
      });
      if (!result.ok) {
        throw new Error(formatRuntimeError(result.data?.detail || result.data?.error || "http_error", LABELS.createFailed));
      }
      await syncLinkedStatus(portalId, portalToken, portalDomain);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : LABELS.createFailed);
    } finally {
      setSubmitting(false);
    }
  };

  const attachExisting = async (targetAccountId: number) => {
    if (!portalId || !portalToken) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      const result = await jsonRequest(`${BASE}/api/v1/bitrix/portals/${portalId}/web/link/attach-existing`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${portalToken}`,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          account_id: targetAccountId,
        }),
      });
      if (!result.ok) {
        throw new Error(formatRuntimeError(result.data?.detail || result.data?.error || "http_error", LABELS.attachFailed));
      }
      await syncLinkedStatus(portalId, portalToken, portalDomain);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : LABELS.attachFailed);
    } finally {
      setSubmitting(false);
    }
  };

  if (ready) {
    return <Outlet context={embeddedContext} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold text-slate-900">Teachbase AI</div>
            <div className="text-sm text-slate-500">
              Bitrix24 embedded
              {portalDomain ? ` · ${portalDomain}` : ""}
            </div>
          </div>
          <a
            href="/app/overview"
            className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
            target="_blank"
            rel="noreferrer"
          >
            {LABELS.openCabinet}
          </a>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          {statusMessage && <div className="mb-4 text-sm text-slate-600">{statusMessage}</div>}
          {errorMessage && <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{errorMessage}</div>}
          {hint && <div className="mb-4 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">{hint}</div>}

          {!precheck && (
            <>
              <div className="mb-4 flex gap-2">
                <button
                  type="button"
                  className={`rounded-full px-4 py-2 text-sm ${authMode === "login" ? "bg-sky-600 text-white" : "border border-slate-200 text-slate-600"}`}
                  onClick={() => setAuthMode("login")}
                >
                  {LABELS.login}
                </button>
                <button
                  type="button"
                  className={`rounded-full px-4 py-2 text-sm ${authMode === "register" ? "bg-sky-600 text-white" : "border border-slate-200 text-slate-600"}`}
                  onClick={() => setAuthMode("register")}
                >
                  {LABELS.register}
                </button>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm text-slate-700">
                  <div className="mb-1">{LABELS.email}</div>
                  <input className="w-full rounded-2xl border border-slate-200 px-4 py-3" value={email} onChange={(e) => setEmail(e.target.value)} />
                </label>
                <label className="text-sm text-slate-700">
                  <div className="mb-1">{LABELS.password}</div>
                  <input className="w-full rounded-2xl border border-slate-200 px-4 py-3" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
                </label>
                {authMode === "register" && (
                  <label className="text-sm text-slate-700 md:col-span-2">
                    <div className="mb-1">{LABELS.company}</div>
                    <input className="w-full rounded-2xl border border-slate-200 px-4 py-3" value={company} onChange={(e) => setCompany(e.target.value)} />
                  </label>
                )}
              </div>
              <div className="mt-4">
                <button
                  type="button"
                  disabled={submitting}
                  className="rounded-full bg-sky-600 px-5 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => void onSubmit()}
                >
                  {LABELS.enter}
                </button>
              </div>
            </>
          )}

          {precheck && (
            <div className="space-y-4">
              <div>
                <div className="text-lg font-semibold text-slate-900">{LABELS.attachTitle}</div>
                <div className="mt-1 text-sm text-slate-600">{LABELS.attachSubtitle}</div>
              </div>

              {precheck.can_create_new_account && (
                <div className="rounded-2xl border border-slate-200 p-4">
                  <div className="font-medium text-slate-900">{LABELS.createAccount}</div>
                  <div className="mt-1 text-sm text-slate-600">{LABELS.createHint}</div>
                  <button
                    type="button"
                    disabled={submitting}
                    className="mt-3 rounded-full bg-sky-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={() => void createAccount()}
                  >
                    {LABELS.createAccount}
                  </button>
                </div>
              )}

              <div className="space-y-3">
                {precheck.attachable_accounts.map((account) => (
                  <div key={account.account_id} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-900">
                          {account.name}
                          {account.account_no ? ` · №${account.account_no}` : ""}
                        </div>
                        <div className="mt-1 text-sm text-slate-500">
                          {LABELS.role}: {account.role} · {LABELS.portals}: {account.bitrix_portals_used}/{account.bitrix_portals_limit}
                        </div>
                        {account.reason && (
                          <div className="mt-1 text-sm text-amber-700">
                            {formatRuntimeError(account.reason, LABELS.attachUnavailable)}
                          </div>
                        )}
                      </div>
                      <button
                        type="button"
                        disabled={!account.attach_allowed || submitting}
                        className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => void attachExisting(account.account_id)}
                      >
                        {LABELS.attachExisting}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export type { EmbeddedBitrixContext };
