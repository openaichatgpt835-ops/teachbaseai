import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

const DEFAULT_WELCOME = "!  Teachbase AI.  ping   pong.";

export function PortalDetailPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["portal", id],
    queryFn: () => api.get(`/v1/admin/portals/${id}`),
    enabled: !!id,
  });

  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [saved, setSaved] = useState(false);

  const putWelcome = useMutation({
    mutationFn: (text: string) =>
      api.put(`/v1/admin/portals/${id}/welcome_message`, { welcome_message: text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal", id] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const [botRegisterResult, setBotRegisterResult] = useState<{
    status: string;
    trace_id?: string;
    bot?: { status: string; bot_id_present?: boolean; error_code?: string; error_description_safe?: string };
    event_urls_sent?: string[];
  } | null>(null);
  const [botCheckResult, setBotCheckResult] = useState<{
    status: string;
    trace_id?: string;
    bot_found_in_bitrix?: boolean;
    error_code?: string;
    bots_count?: number;
  } | null>(null);
  const [provisionWelcomeResult, setProvisionWelcomeResult] = useState<{
    status: string;
    trace_id?: string;
    ok_count?: number;
    fail_count?: number;
    results?: { user_id: number; ok: boolean; error_code?: string }[];
  } | null>(null);
  const [fixHandlersResult, setFixHandlersResult] = useState<{
    ok: boolean;
    trace_id?: string;
    bot_id?: number;
    error_code?: string;
    notes?: string;
  } | null>(null);
  const [pingResult, setPingResult] = useState<{
    ok: boolean;
    trace_id?: string;
    user_id?: number;
    dialog_id?: string;
    error_code?: string;
    notes?: string;
  } | null>(null);
  const [refreshAuthResult, setRefreshAuthResult] = useState<{
    ok: boolean;
    trace_id?: string;
    portal_id?: number;
    error_code?: string;
    notes?: string;
    expires_in?: number;
    expires_at?: string;
  } | null>(null);
  const [authSaveResult, setAuthSaveResult] = useState<{
    ok: boolean;
    client_id_masked?: string;
    client_secret_len?: number;
    client_secret_sha256?: string;
  } | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [monthlyLimit, setMonthlyLimit] = useState<string>("");

  const { data: botStatus, refetch: refetchBotStatus } = useQuery({
    queryKey: ["portal", id, "bot/status"],
    queryFn: () => api.get(`/v1/admin/portals/${id}/bot/status?limit=10`),
    enabled: !!id,
  });
  const { data: authStatus, refetch: refetchAuthStatus } = useQuery({
    queryKey: ["portal", id, "auth/status"],
    queryFn: () => api.get(`/v1/admin/portals/${id}/auth/status`),
    enabled: !!id,
  });
  const { data: billingSummary, refetch: refetchBillingSummary } = useQuery({
    queryKey: ["portal", id, "billing/summary"],
    queryFn: () => api.get(`/v1/admin/billing/portals/${id}/summary`),
    enabled: !!id,
  });
  const { data: billingUsage, refetch: refetchBillingUsage } = useQuery({
    queryKey: ["portal", id, "billing/usage"],
    queryFn: () => api.get(`/v1/admin/billing/usage?portal_id=${id}&limit=50`),
    enabled: !!id,
  });
  useEffect(() => {
    const lim = (billingSummary as { limit_requests?: number | null } | undefined)?.limit_requests;
    if (lim != null) setMonthlyLimit(String(lim));
  }, [billingSummary]);

  const botRegister = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/bot/register`),
    onSuccess: (res: unknown) => {
      setBotRegisterResult(res as typeof botRegisterResult);
      queryClient.invalidateQueries({ queryKey: ["portal", id] });
      refetchBotStatus();
    },
    onError: () => {
      setBotRegisterResult({ status: "error" });
    },
  });

  const botCheck = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/bot/check`),
    onSuccess: (res: unknown) => setBotCheckResult(res as typeof botCheckResult),
    onError: () => setBotCheckResult({ status: "error" }),
  });

  const provisionWelcome = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/bot/provision_welcome`),
    onSuccess: (res: unknown) => setProvisionWelcomeResult(res as typeof provisionWelcomeResult),
    onError: () => setProvisionWelcomeResult({ status: "error" }),
  });

  const botFixHandlers = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/bot/fix-handlers`),
    onSuccess: (res: unknown) => {
      setFixHandlersResult(res as typeof fixHandlersResult);
      queryClient.invalidateQueries({ queryKey: ["portal", id] });
      refetchBotStatus();
    },
    onError: () => setFixHandlersResult({ ok: false }),
  });

  const botPing = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/bot/ping`),
    onSuccess: (res: unknown) => setPingResult(res as typeof pingResult),
    onError: () => setPingResult({ ok: false }),
  });
  const refreshAuth = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/auth/refresh-bitrix`),
    onSuccess: (res: unknown) => {
      setRefreshAuthResult(res as typeof refreshAuthResult);
      refetchAuthStatus();
    },
    onError: () => setRefreshAuthResult({ ok: false, notes: "   " }),
  });
  const saveAuth = useMutation({
    mutationFn: () => api.post(`/v1/admin/portals/${id}/auth/set-local-credentials`, {
      client_id: clientId.trim(),
      client_secret: clientSecret,
    }),
    onSuccess: (res: unknown) => {
      setAuthSaveResult(res as typeof authSaveResult);
      setClientSecret("");
      refetchAuthStatus();
    },
    onError: () => setAuthSaveResult({ ok: false }),
  });
  const saveLimit = useMutation({
    mutationFn: () => api.post(`/v1/admin/billing/portals/${id}/limit`, {
      monthly_request_limit: monthlyLimit ? Number(monthlyLimit) : null,
    }),
    onSuccess: () => {
      refetchBillingSummary();
    },
  });

  if (isLoading) return <div>...</div>;
  if (error) return <div className="text-red-600">: {String(error)}</div>;
  if (!data) return null;

  const p = data as {
    id: number;
    domain: string;
    status: string;
    member_id?: string;
    allowed_user_ids?: string[];
    welcome_message?: string;
  };
  const allowed = p.allowed_user_ids || [];
  const currentWelcome = p.welcome_message ?? DEFAULT_WELCOME;
  const welcomeValue = welcomeMessage || currentWelcome;

  return (
    <div>
      <div className="mb-4">
        <Link to="/admin/portals" className="text-blue-600 hover:underline"></Link>
      </div>
      <h1 className="text-2xl font-bold mb-6">{p.domain}</h1>
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <dl className="grid grid-cols-2 gap-4">
          <dt className="text-gray-500">ID</dt>
          <dd>{p.id}</dd>
          <dt className="text-gray-500"></dt>
          <dd>{p.status}</dd>
          <dt className="text-gray-500">Member ID</dt>
          <dd>{p.member_id || ""}</dd>
        </dl>
      </div>
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="font-semibold mb-2"> ()</h2>
        <div className="text-sm text-gray-600 mb-3">
                 .
        </div>
        {billingSummary && (
          <div className="mb-4">
            <div className="text-sm">
              : <strong>{(billingSummary as { used_requests?: number }).used_requests ?? 0}</strong>
              {" / "}
              <strong>{(billingSummary as { limit_requests?: number | null }).limit_requests ?? ""}</strong>
              {"  "}
              tokens: {(billingSummary as { tokens_total?: number }).tokens_total ?? 0}
              {"  "}
              cost: {((billingSummary as { cost_rub?: number }).cost_rub ?? 0).toFixed(2)} 
            </div>
            <div className="mt-2 h-2 bg-gray-200 rounded">
              <div
                className="h-2 bg-blue-600 rounded"
                style={{ width: `${(billingSummary as { percent?: number }).percent ?? 0}%` }}
              />
            </div>
          </div>
        )}
        <div className="flex items-center gap-2">
          <input
            className="border rounded px-3 py-2 text-sm w-40"
            placeholder=" /"
            value={monthlyLimit}
            onChange={(e) => setMonthlyLimit(e.target.value)}
          />
          <button
            type="button"
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            disabled={saveLimit.isPending}
            onClick={() => saveLimit.mutate()}
          >
             
          </button>
          <button
            type="button"
            className="px-3 py-2 border rounded"
            onClick={() => {
              refetchBillingSummary();
              refetchBillingUsage();
            }}
          >
            
          </button>
        </div>
        {billingUsage && (
          <div className="mt-4 overflow-x-auto text-xs border rounded">
            <table className="min-w-full">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-2 py-1 text-left">created_at</th>
                  <th className="px-2 py-1 text-left">user_id</th>
                  <th className="px-2 py-1 text-left">tokens</th>
                  <th className="px-2 py-1 text-left">cost </th>
                  <th className="px-2 py-1 text-left">status</th>
                  <th className="px-2 py-1 text-left">error</th>
                </tr>
              </thead>
              <tbody>
                {(billingUsage as { items?: Array<{ created_at?: string; user_id?: string; tokens_total?: number; cost_rub?: number; status?: string; error_code?: string }> }).items?.map((r, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-2 py-1">{r.created_at ?? ""}</td>
                    <td className="px-2 py-1">{r.user_id ?? ""}</td>
                    <td className="px-2 py-1">{r.tokens_total ?? ""}</td>
                    <td className="px-2 py-1">{(r.cost_rub ?? 0).toFixed(2)}</td>
                    <td className="px-2 py-1">{r.status ?? ""}</td>
                    <td className="px-2 py-1">{r.error_code ?? ""}</td>
                  </tr>
                )) ?? null}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="font-semibold mb-2"></h2>
        <p className="text-sm text-gray-600 mb-2">
                     provision.
        </p>
        <textarea
          className="w-full border rounded px-3 py-2 text-sm min-h-[100px]"
          value={welcomeValue}
          onChange={(e) => {
            setWelcomeMessage(e.target.value);
          }}
          placeholder={DEFAULT_WELCOME}
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            disabled={putWelcome.isPending}
            onClick={() => putWelcome.mutate(welcomeValue.trim() || DEFAULT_WELCOME)}
          >
            
          </button>
          {saved && <span className="text-green-600 text-sm"></span>}
          {putWelcome.isError && (
            <span className="text-red-600 text-sm">{String(putWelcome.error)}</span>
          )}
        </div>
        <div className="mt-6 pt-4 border-t">
          <h3 className="font-semibold mb-2">Bitrix OAuth ( )</h3>
          <div className="text-sm text-gray-600 mb-2">
                client_id/client_secret.     ().
          </div>
          {authStatus && (
            <div className="mb-3 text-sm">
              creds: <strong>{(authStatus as { has_local_client_id?: boolean; has_local_client_secret?: boolean }).has_local_client_id && (authStatus as { has_local_client_secret?: boolean }).has_local_client_secret ? "ok" : "missing"}</strong>
              {"  "}
              token: <strong>{(authStatus as { expired?: boolean }).expired ? "expired" : "valid"}</strong>
              {"  "}
              source: <strong>{(authStatus as { using_global_env?: boolean }).using_global_env ? "env" : "local"}</strong>
              {(authStatus as { expires_at?: string }).expires_at && (
                <span className="ml-2 text-gray-500">expires_at: {(authStatus as { expires_at?: string }).expires_at}</span>
              )}
            </div>
          )}
          {authStatus && (authStatus as { events_url_expected?: string }).events_url_expected && (
            <div className="mb-2 text-xs text-gray-600">
              expected handler URL: {(authStatus as { events_url_expected?: string }).events_url_expected}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              className="border rounded px-3 py-2 text-sm"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="client_id (local.*)"
            />
            <input
              className="border rounded px-3 py-2 text-sm"
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder="client_secret"
            />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={saveAuth.isPending || !clientId.trim() || !clientSecret}
              onClick={() => saveAuth.mutate()}
            >
              
            </button>
            <button
              type="button"
              className="px-4 py-2 bg-sky-600 text-white rounded hover:bg-sky-700 disabled:opacity-50"
              disabled={refreshAuth.isPending}
              onClick={() => refreshAuth.mutate()}
            >
              Test refresh
            </button>
          </div>
          {authSaveResult && (
            <div className="mt-2 text-sm">
              {authSaveResult.ok ? (
                <span className="text-green-600">. client_id: {authSaveResult.client_id_masked}</span>
              ) : (
                <span className="text-amber-600">   credentials</span>
              )}
            </div>
          )}
          {refreshAuthResult && (
            <div className="mt-2 text-sm">
              {refreshAuthResult.ok ? (
                <span className="text-green-600">Refresh OK (expires_in: {refreshAuthResult.expires_in ?? ""}s)</span>
              ) : (
                <span className="text-amber-600">Refresh error: {refreshAuthResult.error_code ?? "unknown"}</span>
              )}
            </div>
          )}
          <h3 className="font-semibold mb-2">Bot provisioning ()</h3>
          {botStatus && (
            <div className="mb-3 text-sm">
              : <strong>{(botStatus as { status?: string }).status ?? ""}</strong>
              {(botStatus as { bot_id?: number }).bot_id != null && (
                <span className="ml-2">bot_id: {(botStatus as { bot_id?: number }).bot_id}</span>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-2 mb-3">
            <button
              type="button"
              className="px-4 py-2 bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50"
              disabled={botRegister.isPending}
              onClick={() => botRegister.mutate()}
            >
                ()
            </button>
            <button
              type="button"
              className="px-4 py-2 bg-slate-600 text-white rounded hover:bg-slate-700 disabled:opacity-50"
              disabled={botCheck.isPending}
              onClick={() => botCheck.mutate()}
            >
               
            </button>
            <button
              type="button"
              className="px-4 py-2 bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-50"
              disabled={botFixHandlers.isPending}
              onClick={() => botFixHandlers.mutate()}
            >
               handler URL
            </button>
            <button
              type="button"
              className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
              disabled={provisionWelcome.isPending || allowed.length === 0}
              onClick={() => provisionWelcome.mutate()}
            >
               welcome  allowlist
            </button>
            <button
              type="button"
              className="px-4 py-2 bg-cyan-600 text-white rounded hover:bg-cyan-700 disabled:opacity-50"
              disabled={botPing.isPending || allowed.length === 0}
              onClick={() => botPing.mutate()}
            >
               
            </button>
          </div>
          {botRegisterResult && (
            <div className="mt-2 p-3 rounded text-sm bg-gray-50">
              {botRegisterResult.status === "ok" && botRegisterResult.bot?.status === "ok" ? (
                <span className="text-green-600">OK. bot_id .</span>
              ) : (
                <div className="text-red-600">
                  : {botRegisterResult.bot?.error_code ?? "unknown"}
                  {botRegisterResult.bot?.error_description_safe && (
                    <div className="mt-1 text-gray-700">{botRegisterResult.bot.error_description_safe}</div>
                  )}
                  {botRegisterResult.trace_id && (
                    <div className="mt-1 text-gray-500">
                      Trace: <Link to={`/admin/traces/${botRegisterResult.trace_id}`} className="text-blue-600 hover:underline">{botRegisterResult.trace_id}</Link>
                    </div>
                  )}
                  {botRegisterResult.event_urls_sent && botRegisterResult.event_urls_sent.length > 0 && (
                    <div className="mt-1 text-gray-500">URLs: {botRegisterResult.event_urls_sent.join(", ")}</div>
                  )}
                </div>
              )}
            </div>
          )}
          {botCheckResult && (
            <div className="mt-2 p-3 rounded text-sm bg-gray-50">
              {botCheckResult.bot_found_in_bitrix ? (
                <span className="text-green-600">   Bitrix (bots: {botCheckResult.bots_count ?? 0})</span>
              ) : (
                <span className="text-amber-600">
                      Bitrix {botCheckResult.error_code ? `(${botCheckResult.error_code})` : ""}
                </span>
              )}
              {botCheckResult.error_code === "bitrix_auth_invalid" && (
                <div className="mt-1 text-amber-700"> Bitrix     .</div>
              )}
              {botCheckResult.trace_id && (
                <div className="mt-1 text-gray-500">
                  Trace: <Link to={`/admin/traces/${botCheckResult.trace_id}`} className="text-blue-600 hover:underline">{botCheckResult.trace_id}</Link>
                </div>
              )}
            </div>
          )}
          {fixHandlersResult && (
            <div className="mt-2 p-3 rounded text-sm bg-gray-50">
              {fixHandlersResult.ok ? (
                <span className="text-green-600">Handler URL  (imbot.update OK). bot_id: {fixHandlersResult.bot_id}</span>
              ) : (
                <span className="text-amber-600">
                  : {fixHandlersResult.error_code ?? "unknown"} {fixHandlersResult.notes ? ` ${fixHandlersResult.notes}` : ""}
                </span>
              )}
              {fixHandlersResult.error_code === "bitrix_auth_invalid" && (
                <div className="mt-1 text-amber-700"> Bitrix     .</div>
              )}
              {fixHandlersResult.trace_id && (
                <div className="mt-1 text-gray-500">
                  Trace: <Link to={`/admin/traces/${fixHandlersResult.trace_id}`} className="text-blue-600 hover:underline">{fixHandlersResult.trace_id}</Link>
                </div>
              )}
            </div>
          )}
          {pingResult && (
            <div className="mt-2 p-3 rounded text-sm bg-gray-50">
              {pingResult.ok ? (
                <>
                  <span className="text-green-600">Ping  (dialog_id: {pingResult.dialog_id})</span>
                  <div className="mt-1 text-gray-600">{pingResult.notes}</div>
                </>
              ) : (
                <span className="text-amber-600">: {pingResult.error_code ?? "unknown"} {pingResult.notes ? ` ${pingResult.notes}` : ""}</span>
              )}
              {pingResult.trace_id && (
                <div className="mt-1 text-gray-500">
                  Trace: <Link to={`/admin/traces/${pingResult.trace_id}`} className="text-blue-600 hover:underline">{pingResult.trace_id}</Link>
                  {"  "}
                  <Link to="/admin/inbound-events" className="text-blue-600 hover:underline">Inbound events</Link>
                </div>
              )}
              {!pingResult.ok && pingResult.error_code === "bitrix_auth_invalid" && (
                <div className="mt-1 text-amber-700"> Bitrix     .</div>
              )}
            </div>
          )}
          {provisionWelcomeResult && provisionWelcomeResult.status !== "error" && (
            <div className="mt-2 p-3 rounded text-sm bg-gray-50">
              OK: {provisionWelcomeResult.ok_count ?? 0}, : {provisionWelcomeResult.fail_count ?? 0}
              {provisionWelcomeResult.trace_id && (
                <div className="mt-1 text-gray-500">Trace: {provisionWelcomeResult.trace_id}</div>
              )}
            </div>
          )}
          {botStatus && (() => {
            const attempts = (botStatus as { last_attempts?: Array<{ trace_id?: string; created_at?: string; status_code?: number; error_code?: string; error_description_safe?: string; event_urls_sent?: string[]; content_type_sent?: string; api_prefix_used?: string; request_shape_json?: unknown; response_shape_json?: unknown }> }).last_attempts ?? [];
            const last = attempts[0];
            return attempts.length > 0 ? (
            <>
            {last && (
              <div className="mt-3 p-3 rounded bg-gray-50 text-sm">
                <div className="font-medium mb-1"> </div>
                {last.error_description_safe && (
                  <div className="text-amber-700">bitrix_error_desc: {last.error_description_safe}</div>
                )}
                {last.event_urls_sent && last.event_urls_sent.length > 0 && (
                  <div className="text-gray-600">URLs: {last.event_urls_sent.join(", ")}</div>
                )}
                {last.content_type_sent && <div className="text-gray-600">content_type_sent: {last.content_type_sent}</div>}
                {last.api_prefix_used != null && <div className="text-gray-600">api_prefix_used: {last.api_prefix_used}</div>}
                {last.trace_id && (
                  <Link to={`/admin/traces/${last.trace_id}`} className="text-blue-600 hover:underline mt-1 inline-block">
                      
                  </Link>
                )}
              </div>
            )}
            <div className="mt-4">
              <h4 className="font-medium mb-2">  imbot.register</h4>
              <div className="overflow-x-auto text-xs border rounded">
                <table className="min-w-full">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-2 py-1 text-left">trace_id</th>
                      <th className="px-2 py-1 text-left">created_at</th>
                      <th className="px-2 py-1 text-left">status_code</th>
                      <th className="px-2 py-1 text-left">error_code</th>
                      <th className="px-2 py-1 text-left">request_shape / response_shape</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attempts.map((a, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-2 py-1 font-mono">
                          {a.trace_id ? (
                            <Link to={`/admin/traces/${a.trace_id}`} className="text-blue-600 hover:underline">{a.trace_id}</Link>
                          ) : ""}
                        </td>
                        <td className="px-2 py-1">{a.created_at ?? ""}</td>
                        <td className="px-2 py-1">{a.status_code ?? ""}</td>
                        <td className="px-2 py-1">{a.error_code ?? ""}</td>
                        <td className="px-2 py-1 max-w-xs truncate">
                          {a.request_shape_json != null || a.response_shape_json != null
                            ? ""
                            : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            </>
            ) : null;
          })()}
          {botStatus && (() => {
            const prepare = (botStatus as { last_prepare_chats?: Array<{ trace_id?: string; created_at?: string; status?: string; total?: number; ok_count?: number; users_failed?: number; failed?: Array<{ user_id?: number; code?: string }> }> }).last_prepare_chats ?? [];
            const lastP = prepare[0];
            return prepare.length > 0 ? (
              <div className="mt-6 pt-4 border-t">
                <h3 className="font-semibold mb-2">Prepare chats (allowlist)</h3>
                {lastP && (
                  <div className="mb-3 p-3 rounded bg-gray-50 text-sm">
                    <div className="font-medium mb-1"> </div>
                    <div>: {lastP.status ?? ""} | : {lastP.total ?? 0} | ok: {lastP.ok_count ?? 0} | failed: {lastP.users_failed ?? 0}</div>
                    {lastP.trace_id && (
                      <Link to={`/admin/traces/${lastP.trace_id}`} className="text-blue-600 hover:underline mt-1 inline-block">  </Link>
                    )}
                  </div>
                )}
                <div className="overflow-x-auto text-xs border rounded">
                  <table className="min-w-full">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="px-2 py-1 text-left">trace_id</th>
                        <th className="px-2 py-1 text-left">created_at</th>
                        <th className="px-2 py-1 text-left">status</th>
                        <th className="px-2 py-1 text-left">total / ok / failed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {prepare.map((row, i) => (
                        <tr key={i} className="border-t">
                          <td className="px-2 py-1 font-mono">
                            {row.trace_id ? (
                              <Link to={`/admin/traces/${row.trace_id}`} className="text-blue-600 hover:underline">{row.trace_id}</Link>
                            ) : ""}
                          </td>
                          <td className="px-2 py-1">{row.created_at ?? ""}</td>
                          <td className="px-2 py-1">{row.status ?? ""}</td>
                          <td className="px-2 py-1">{row.total ?? ""} / {row.ok_count ?? ""} / {row.users_failed ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null;
          })()}
        </div>
      </div>
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="font-semibold mb-2"> (allowlist)</h2>
        <p className="text-sm text-gray-600 mb-2">
           Bitrix user_id    : {allowed.length} .
        </p>
        {allowed.length > 0 ? (
          <ul className="list-disc list-inside text-sm">
            {allowed.slice(0, 20).map((uid) => (
              <li key={uid}>{uid}</li>
            ))}
            {allowed.length > 20 && <li>   {allowed.length - 20}</li>}
          </ul>
        ) : (
          <p className="text-gray-500 text-sm"> .      Bitrix24.</p>
        )}
      </div>
    </div>
  );
}
