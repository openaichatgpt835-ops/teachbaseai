import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { HelpTriggerButton } from "../../components/ui/HelpTriggerButton";
import { InspectorPanel } from "../../components/ui/InspectorPanel";
import { Panel, PanelBody, PanelHeader } from "../../components/ui/Panel";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { ToastNotice } from "../../components/ui/ToastNotice";
import { getActiveAccountId } from "./auth";
import { fetchPortal, fetchWeb, getWebPortalInfo } from "./auth";
import { fetchUsersAccessCenter, fetchUsersAccessInvites, fetchUsersAccessMe } from "./users-access-v2/api";
import type { UsersAccessGroupItem, UsersAccessInviteItem, UsersAccessMeContext, UsersAccessUserItem } from "./users-access-v2/types";

const CHECKBOX_CLASS = "h-4 w-4 rounded border-slate-300 accent-sky-600";

type TabKey = "people" | "groups" | "defaults" | "invites";
type UserDrawerState = { open: boolean; user: UsersAccessUserItem | null; tab: "overview" | "settings" };
type GroupDrawerState = { open: boolean; group: UsersAccessGroupItem | null; tab: "overview" | "members" };
type CreateUserDialogState = {
  open: boolean;
  displayName: string;
  login: string;
  email: string;
  password: string;
  role: "member" | "admin";
  saving: boolean;
  message: string;
};
type GroupDialogState = {
  open: boolean;
  mode: "create" | "edit";
  id: number | null;
  name: string;
  kind: "staff";
  membershipIds: number[];
  saving: boolean;
  message: string;
};
type InviteRole = "admin" | "member";

const TAB_OPTIONS = [
  { value: "people", label: "Сотрудники" },
  { value: "groups", label: "Группы" },
  { value: "defaults", label: "Доступ по умолчанию" },
  { value: "invites", label: "Приглашения" },
];

export function WebUsersPageV2() {
  const [accountId, setAccountId] = useState<number>(getActiveAccountId());
  const [meCtx, setMeCtx] = useState<UsersAccessMeContext | null>(null);
  const [users, setUsers] = useState<UsersAccessUserItem[]>([]);
  const [groups, setGroups] = useState<UsersAccessGroupItem[]>([]);
  const [invites, setInvites] = useState<UsersAccessInviteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("people");
  const [peopleSearch, setPeopleSearch] = useState("");
  const [peopleType, setPeopleType] = useState<"all" | "member" | "admin" | "owner">("all");
  const [peopleChannel, setPeopleChannel] = useState<"all" | "web" | "bitrix" | "telegram">("all");
  const [peopleStatus, setPeopleStatus] = useState<"all" | "active" | "invited" | "blocked" | "deleted">("all");
  const [peopleGroup, setPeopleGroup] = useState<number>(0);
  const [groupsSearch, setGroupsSearch] = useState("");
  const [groupsUsage, setGroupsUsage] = useState<"all" | "filled" | "empty">("all");
  const [howItWorksOpen, setHowItWorksOpen] = useState(false);
  const [userDrawer, setUserDrawer] = useState<UserDrawerState>({ open: false, user: null, tab: "overview" });
  const [groupDrawer, setGroupDrawer] = useState<GroupDrawerState>({ open: false, group: null, tab: "overview" });
  const [createUserDialog, setCreateUserDialog] = useState<CreateUserDialogState>({
    open: false,
    displayName: "",
    login: "",
    email: "",
    password: "",
      role: "member",
    saving: false,
    message: "",
  });
  const [userActionMessage, setUserActionMessage] = useState("");
  const [groupActionMessage, setGroupActionMessage] = useState("");
  const [savingMembershipId, setSavingMembershipId] = useState<number>(0);
  const [savingGroupMembershipKey, setSavingGroupMembershipKey] = useState("");
  const [telegramDrafts, setTelegramDrafts] = useState<Record<number, string>>({});
  const [bitrixAllowDrafts, setBitrixAllowDrafts] = useState<Record<number, boolean>>({});
  const [bitrixTelegramDrafts, setBitrixTelegramDrafts] = useState<Record<number, string>>({});
  const [bitrixSelectedUsers, setBitrixSelectedUsers] = useState<number[]>([]);
  const [bitrixSavingMembershipId, setBitrixSavingMembershipId] = useState<number>(0);
  const [groupDialog, setGroupDialog] = useState<GroupDialogState>({
    open: false,
    mode: "create",
    id: null,
    name: "",
    kind: "staff",
    membershipIds: [],
    saving: false,
    message: "",
  });
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<InviteRole>("member");
  const [inviteActionMessage, setInviteActionMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      const me = await fetchUsersAccessMe();
      if (!mounted) return;
      setMeCtx(me);
      const nextAccountId = Number(me?.account?.id || accountId || 0);
      if (!nextAccountId) {
        setLoading(false);
        setMessage("Не удалось определить аккаунт.");
        return;
      }
      setAccountId(nextAccountId);
      const [accessCenter, nextInvites] = await Promise.all([
        fetchUsersAccessCenter(nextAccountId),
        fetchUsersAccessInvites(nextAccountId),
      ]);
      if (!mounted) return;
      if (!accessCenter) {
        setMessage("Не удалось загрузить пользователей и группы.");
        setLoading(false);
        return;
      }
      const nextUsers = Array.isArray(accessCenter.items) ? accessCenter.items : [];
      setUsers(nextUsers);
      setGroups(Array.isArray(accessCenter.groups) ? accessCenter.groups : []);
      setInvites(nextInvites);
      setTelegramDrafts(buildTelegramDrafts(nextUsers));
      const bitrixState = buildBitrixAccessState(nextUsers);
      setBitrixAllowDrafts(bitrixState.allowMap);
      setBitrixTelegramDrafts(bitrixState.telegramMap);
      setBitrixSelectedUsers(bitrixState.selectedIds);
      setMessage("");
      setLoading(false);
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const staffUsers = useMemo(() => users.filter((user) => user.role !== "client"), [users]);

  const peopleRows = useMemo(() => {
    const query = peopleSearch.trim().toLowerCase();
    return staffUsers.filter((user) => {
      if (peopleType !== "all" && user.role !== peopleType) return false;
      if (peopleStatus !== "all" && user.status !== peopleStatus) return false;
      if (peopleChannel === "web" && !user.web) return false;
      if (peopleChannel === "bitrix" && (!user.bitrix || user.bitrix.length === 0)) return false;
      if (peopleChannel === "telegram" && (!user.telegram || user.telegram.length === 0)) return false;
      if (peopleGroup > 0 && !(user.groups || []).some((group) => group.id === peopleGroup)) return false;
      if (!query) return true;
      const haystack = [user.display_name, user.web?.email, user.web?.login, ...(user.groups || []).map((group) => group.name)]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [peopleSearch, staffUsers, peopleType, peopleStatus, peopleChannel, peopleGroup]);

  const visibleGroups = useMemo(() => {
    const query = groupsSearch.trim().toLowerCase();
    return groups.filter((group) => {
      if (group.kind !== "staff") return false;
      if (groupsUsage === "filled" && group.membership_ids.length === 0) return false;
      if (groupsUsage === "empty" && group.membership_ids.length > 0) return false;
      if (!query) return true;
      return group.name.toLowerCase().includes(query);
    });
  }, [groups, groupsSearch, groupsUsage]);

  const staffUsersCount = staffUsers.length;
  const adminUsersCount = staffUsers.filter((u) => u.role === "admin" || u.role === "owner").length;
  const telegramLinkedCount = staffUsers.filter((u) => Array.isArray(u.telegram) && u.telegram.length > 0).length;
  const bitrixLinkedCount = staffUsers.filter((u) => Array.isArray(u.bitrix) && u.bitrix.length > 0).length;
  const canInviteUsers = !!meCtx?.membership?.can_invite_users;
  const canManageSettings = !!meCtx?.membership?.can_manage_settings;

  const reloadAccessData = async () => {
    if (!accountId) return;
    const [accessCenter, nextInvites] = await Promise.all([
      fetchUsersAccessCenter(accountId),
      fetchUsersAccessInvites(accountId),
    ]);
    if (!accessCenter) {
      setMessage("Не удалось обновить пользователей и группы.");
      return;
    }
    const nextUsers = Array.isArray(accessCenter.items) ? accessCenter.items : [];
    setUsers(nextUsers);
    setGroups(Array.isArray(accessCenter.groups) ? accessCenter.groups : []);
    setInvites(nextInvites);
    setTelegramDrafts(buildTelegramDrafts(nextUsers));
    const bitrixState = buildBitrixAccessState(nextUsers);
    setBitrixAllowDrafts(bitrixState.allowMap);
    setBitrixTelegramDrafts(bitrixState.telegramMap);
    setBitrixSelectedUsers(bitrixState.selectedIds);
    setUserDrawer((current) => {
      if (!current.user) return current;
      const fresh = nextUsers.find((item) => item.membership_id === current.user?.membership_id) || null;
      return { ...current, user: fresh };
    });
  };

  const openCreateGroupDialog = () => {
    setGroupDialog({
      open: true,
      mode: "create",
      id: null,
      name: "",
      kind: "staff",
      membershipIds: [],
      saving: false,
      message: "",
    });
  };

  const openEditGroupDialog = (group: UsersAccessGroupItem) => {
    setGroupDialog({
      open: true,
      mode: "edit",
      id: group.id,
      name: group.name,
      kind: "staff",
      membershipIds: [...group.membership_ids].sort((a, b) => a - b),
      saving: false,
      message: "",
    });
  };

  const saveGroup = async () => {
    if (!accountId || !canManageSettings) {
      setGroupDialog((current) => ({ ...current, message: "Недостаточно прав для управления группами." }));
      return;
    }
    const name = groupDialog.name.trim();
    if (!name) {
      setGroupDialog((current) => ({ ...current, message: "Укажи название группы." }));
      return;
    }
    setGroupDialog((current) => ({ ...current, saving: true, message: "" }));
    try {
      const path = groupDialog.mode === "edit" && groupDialog.id
        ? `/api/v2/web/accounts/${accountId}/user-groups/${groupDialog.id}`
        : `/api/v2/web/accounts/${accountId}/user-groups`;
      const method = groupDialog.mode === "edit" ? "PATCH" : "POST";
      const res = await fetchWeb(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          kind: groupDialog.kind,
          membership_ids: groupDialog.membershipIds,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setGroupDialog((current) => ({ ...current, saving: false, message: data?.detail || data?.message || "Ошибка сохранения группы." }));
        return;
      }
      await reloadAccessData();
      setGroupDialog({
        open: false,
        mode: "create",
        id: null,
        name: "",
        kind: "staff",
        membershipIds: [],
        saving: false,
        message: "",
      });
      setGroupActionMessage(method === "POST" ? "Группа создана." : "Группа обновлена.");
    } catch {
      setGroupDialog((current) => ({ ...current, saving: false, message: "Ошибка сохранения группы." }));
    }
  };

  const deleteGroup = async (groupId: number) => {
    if (!accountId || !canManageSettings) {
      setGroupActionMessage("Недостаточно прав для удаления группы.");
      return;
    }
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/user-groups/${groupId}`, { method: "DELETE" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setGroupActionMessage(data?.detail || data?.message || "Ошибка удаления группы.");
      return;
    }
    await reloadAccessData();
    setGroupDrawer({ open: false, group: null, tab: "overview" });
    setGroupActionMessage("Группа удалена.");
  };

  const patchMembership = async (membershipId: number, patch: Record<string, unknown>) => {
    if (!accountId || !canManageSettings) {
      setUserActionMessage("Недостаточно прав для изменения ролей и прав.");
      return;
    }
    setSavingMembershipId(membershipId);
    setUserActionMessage("");
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/memberships/${membershipId}/permissions`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setUserActionMessage(data?.detail || data?.message || "Ошибка сохранения прав.");
        return;
      }
      await reloadAccessData();
      setUserActionMessage("Изменения сохранены.");
    } finally {
      setSavingMembershipId(0);
    }
  };

  const saveMembershipTelegram = async (membershipId: number) => {
    if (!accountId || !canInviteUsers) {
      setUserActionMessage("Недостаточно прав для привязки Telegram.");
      return;
    }
    setSavingMembershipId(membershipId);
    setUserActionMessage("");
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/memberships/${membershipId}/telegram`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_username: telegramDrafts[membershipId]?.trim().replace(/^@+/, "") || null }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setUserActionMessage(data?.detail || data?.message || "Ошибка сохранения Telegram.");
        return;
      }
      await reloadAccessData();
      setUserActionMessage("Telegram сохранён.");
    } finally {
      setSavingMembershipId(0);
    }
  };

  const createManualUser = async () => {
    if (!accountId || !canInviteUsers) {
      setCreateUserDialog((current) => ({ ...current, message: "Недостаточно прав для создания пользователей." }));
      return;
    }
    const login = createUserDialog.login.trim();
    const password = createUserDialog.password.trim();
    if (!login || !password) {
      setCreateUserDialog((current) => ({ ...current, message: "Для ручного создания нужны логин и пароль." }));
      return;
    }
    setCreateUserDialog((current) => ({ ...current, saving: true, message: "" }));
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/users/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: createUserDialog.displayName.trim() || null,
          login,
          email: createUserDialog.email.trim() || null,
          password,
          role: createUserDialog.role,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setCreateUserDialog((current) => ({ ...current, saving: false, message: data?.detail || data?.message || "Ошибка создания пользователя." }));
        return;
      }
      await reloadAccessData();
      setCreateUserDialog({
        open: false,
        displayName: "",
        login: "",
        email: "",
        password: "",
        role: "member",
        saving: false,
        message: "",
      });
      setUserActionMessage("Пользователь создан.");
    } catch {
      setCreateUserDialog((current) => ({ ...current, saving: false, message: "Ошибка создания пользователя." }));
    }
  };

  const deleteUser = async (userId: number) => {
    if (!accountId || !canManageSettings) {
      setUserActionMessage("Недостаточно прав для удаления пользователя.");
      return;
    }
    setUserActionMessage("");
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/users/${userId}`, { method: "DELETE" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setUserActionMessage(data?.detail || data?.message || "Ошибка удаления пользователя.");
      return;
    }
    await reloadAccessData();
    setUserDrawer({ open: false, user: null, tab: "overview" });
    setUserActionMessage("Пользователь удалён.");
  };

  const toggleUserGroupMembership = async (user: UsersAccessUserItem, group: UsersAccessGroupItem, checked: boolean) => {
    if (!accountId || !canManageSettings) {
      setUserActionMessage("Недостаточно прав для управления группами пользователя.");
      return;
    }
    const key = `${user.membership_id}:${group.id}`;
    setSavingGroupMembershipKey(key);
    setUserActionMessage("");
    try {
      const nextIds = new Set(group.membership_ids || []);
      if (checked) nextIds.add(user.membership_id);
      else nextIds.delete(user.membership_id);
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/user-groups/${group.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: group.name,
          kind: group.kind,
          membership_ids: Array.from(nextIds).sort((a, b) => a - b),
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setUserActionMessage(data?.detail || data?.message || "Ошибка обновления групп пользователя.");
        return;
      }
      await reloadAccessData();
      setUserActionMessage("Группы пользователя обновлены.");
    } finally {
      setSavingGroupMembershipKey("");
    }
  };

  const saveBitrixAccess = async (membershipId: number) => {
    const user = users.find((item) => item.membership_id === membershipId);
    const portalId = Number(user?.access_center?.portal_id || getWebPortalInfo().portalId || 0);
    if (!portalId) {
      setUserActionMessage("Не удалось определить портал Bitrix.");
      return;
    }
    const bitrixIds = (user?.access_center?.bitrix_user_ids || []).map((value) => Number(value)).filter((value) => Number.isFinite(value));
    if (bitrixIds.length === 0) {
      setUserActionMessage("Bitrix не привязан.");
      return;
    }
    const nextSelected = new Set(bitrixSelectedUsers);
    bitrixIds.forEach((id) => {
      if (bitrixAllowDrafts[membershipId]) nextSelected.add(id);
      else nextSelected.delete(id);
    });
    const nextTelegramMap: Record<number, string> = {};
    users.forEach((item) => {
      const ids = (item.access_center?.bitrix_user_ids || []).map((value) => Number(value)).filter((value) => Number.isFinite(value));
      const username = (item.membership_id === membershipId ? bitrixTelegramDrafts[membershipId] : bitrixTelegramDrafts[item.membership_id]) || "";
      ids.forEach((id) => {
        if (username.trim()) nextTelegramMap[id] = username.trim().replace(/^@+/, "");
      });
    });
    const payloadItems = Array.from(nextSelected).map((id) => ({ user_id: id, telegram_username: nextTelegramMap[id] || null }));
    setBitrixSavingMembershipId(membershipId);
    setUserActionMessage("");
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/users`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: payloadItems }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setUserActionMessage(data?.detail || data?.error || "Ошибка сохранения Bitrix.");
        return;
      }
      await reloadAccessData();
      setUserActionMessage("Права Bitrix сохранены.");
    } finally {
      setBitrixSavingMembershipId(0);
    }
  };

  const createInvite = async () => {
    if (!accountId || !canInviteUsers) {
      setInviteActionMessage("Недостаточно прав для приглашений.");
      return;
    }
    const email = inviteEmail.trim();
    if (!email) {
      setInviteActionMessage("Укажи email.");
      return;
    }
    setInviteActionMessage("");
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/invites/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role: inviteRole, expires_days: 7 }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setInviteActionMessage(data?.detail || data?.message || "Ошибка отправки приглашения.");
      return;
    }
    setInviteEmail("");
    await reloadAccessData();
    setInviteActionMessage("Приглашение отправлено.");
  };

  const revokeInvite = async (id: number) => {
    if (!accountId || !canInviteUsers) {
      setInviteActionMessage("Недостаточно прав для приглашений.");
      return;
    }
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/invites/${id}/revoke`, { method: "POST" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setInviteActionMessage(data?.detail || data?.message || "Ошибка отзыва приглашения.");
      return;
    }
    await reloadAccessData();
    setInviteActionMessage("Приглашение отозвано.");
  };

  const copyInviteLink = async (url: string | null | undefined) => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setInviteActionMessage("Ссылка приглашения скопирована.");
    } catch {
      setInviteActionMessage("Не удалось скопировать ссылку.");
    }
  };

  return (
    <div className="space-y-5">
      <HowItWorksDialog open={howItWorksOpen} onOpenChange={setHowItWorksOpen} />
      <CreateUserDialog
        state={createUserDialog}
        onOpenChange={(open) => {
          if (!open) {
            setCreateUserDialog({
              open: false,
              displayName: "",
              login: "",
              email: "",
              password: "",
              role: "member",
              saving: false,
              message: "",
            });
            return;
          }
          setCreateUserDialog((current) => ({ ...current, open }));
        }}
        onChange={(patch) => setCreateUserDialog((current) => ({ ...current, ...patch }))}
        onSubmit={() => void createManualUser()}
      />
      <GroupDialog
        state={groupDialog}
        users={users}
        onOpenChange={(open) => {
          if (!open) {
            setGroupDialog((current) => ({ ...current, open: false, saving: false, message: "" }));
          }
        }}
        onChange={(patch) => setGroupDialog((current) => ({ ...current, ...patch }))}
        onToggleMembership={(membershipId, checked) =>
          setGroupDialog((current) => {
            const next = new Set(current.membershipIds);
            if (checked) next.add(membershipId);
            else next.delete(membershipId);
            return { ...current, membershipIds: Array.from(next).sort((a, b) => a - b) };
          })
        }
        onSubmit={() => void saveGroup()}
      />

      <Panel tone="elevated" className="border-slate-200">
        <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Управление доступом аккаунта</div>
              <h1 className="mt-2 text-[30px] font-semibold leading-tight text-slate-950">Пользователи и доступы</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Внутренние пользователи, группы сотрудников и базовые права аккаунта. Клиентский бот и доступ к клиентским материалам настраиваются отдельно — в интеграциях и базе знаний.
              </p>
            </div>
            <HelpTriggerButton onClick={() => setHowItWorksOpen(true)} className="shrink-0" />
          </div>
      </Panel>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl value={activeTab} options={TAB_OPTIONS} onChange={(value) => setActiveTab(value as TabKey)} />
        {activeTab === "people" ? <Button variant="primary" size="sm" onClick={() => setCreateUserDialog((current) => ({ ...current, open: true }))} disabled={!canInviteUsers}>Добавить сотрудника</Button> : null}
        {activeTab === "groups" ? <Button variant="primary" size="sm" onClick={openCreateGroupDialog} disabled={!canManageSettings}>Создать группу</Button> : null}
      </div>

      <div className="pointer-events-none fixed right-8 top-20 z-40 flex max-w-[420px] flex-col gap-3">
        <ToastNotice message={message} tone="error" onClose={() => setMessage("")} />
        <ToastNotice message={userActionMessage} onClose={() => setUserActionMessage("")} />
        <ToastNotice message={groupActionMessage} onClose={() => setGroupActionMessage("")} />
        <ToastNotice message={inviteActionMessage} onClose={() => setInviteActionMessage("")} />
      </div>

      {activeTab === "people" ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-4">
            <PeopleSummaryPanel staffUsersCount={staffUsersCount} adminUsersCount={adminUsersCount} telegramLinkedCount={telegramLinkedCount} bitrixLinkedCount={bitrixLinkedCount} />
            <Panel tone="elevated" className="border-slate-200">
              <PanelHeader title="Сотрудники" subtitle="Внутренние пользователи аккаунта, их роли, каналы и группы сотрудников." />
              <PanelBody className="space-y-4">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,0.75fr))]">
                  <SearchInput value={peopleSearch} onChange={setPeopleSearch} placeholder="Поиск по имени, email, логину и группам" />
                  <SelectBox value={peopleType} onChange={setPeopleType} options={[["all", "Все роли"], ["member", "Сотрудники"], ["admin", "Администраторы"], ["owner", "Владельцы"]]} />
                  <SelectBox value={peopleChannel} onChange={setPeopleChannel} options={[["all", "Все каналы"], ["web", "Веб"], ["bitrix", "Bitrix"], ["telegram", "Telegram"]]} />
                  <SelectBox value={peopleGroup} onChange={(value) => setPeopleGroup(Number(value))} options={[[0, "Все группы"], ...groups.filter((group) => group.kind === "staff").map((group) => [group.id, group.name] as [number, string])]} />
                  <SelectBox value={peopleStatus} onChange={setPeopleStatus} options={[["all", "Все статусы"], ["active", "Активные"], ["invited", "Приглашены"], ["blocked", "Заблокированы"], ["deleted", "Удалены"]]} />
                </div>
                <div className="space-y-3">
                  {loading ? <EmptyPanel title="Загружаю пользователей" body="Собираю состав аккаунта, каналы и группы." /> : null}
                  {!loading && peopleRows.length === 0 ? <EmptyPanel title="Сотрудники не найдены" body="Измени фильтры или добавь первого сотрудника." /> : null}
                  {!loading && peopleRows.map((user) => (
                    <button key={user.membership_id} type="button" onClick={() => setUserDrawer({ open: true, user, tab: "overview" })} className="grid w-full gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-3.5 text-left transition hover:border-sky-200 hover:bg-sky-50/40 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.95fr)_110px]">
                      <div className="min-w-0">
                        <div className="truncate text-[15px] font-semibold text-slate-950">{user.display_name || "Без имени"}</div>
                        <div className="mt-1 truncate text-sm text-slate-500">{user.web?.email || user.web?.login || "Локальный пользователь без веб-учетки"}</div>
                      </div>
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap gap-2">
                          <Badge tone={user.role === "admin" || user.role === "owner" ? "amber" : "sky"}>{roleLabel(user.role)}</Badge>
                          <StatusBadge status={user.status} />
                        </div>
                        <div className="flex flex-wrap gap-2">{renderIdentityBadges(user)}</div>
                        <div className="flex flex-wrap gap-2">{renderGroupBadges(user.groups)}</div>
                      </div>
                      <div className="flex items-start justify-end"><Button size="sm" variant="ghost">Открыть</Button></div>
                    </button>
                  ))}
                </div>
              </PanelBody>
            </Panel>
          </div>
          <UserInspector
            state={userDrawer}
            canInviteUsers={canInviteUsers}
            canManageSettings={canManageSettings}
            telegramDrafts={telegramDrafts}
            bitrixAllowDrafts={bitrixAllowDrafts}
            bitrixTelegramDrafts={bitrixTelegramDrafts}
            bitrixSavingMembershipId={bitrixSavingMembershipId}
            savingMembershipId={savingMembershipId}
            savingGroupMembershipKey={savingGroupMembershipKey}
            groups={groups}
            onOpenChange={(open) => setUserDrawer((current) => ({ ...current, open }))}
            onTabChange={(tab) => setUserDrawer((current) => ({ ...current, tab }))}
            onRoleChange={(membershipId, role) => void patchMembership(membershipId, { role })}
            onKbAccessChange={(membershipId, kbAccess) => void patchMembership(membershipId, { kb_access: kbAccess })}
            onToggleFlag={(membershipId, field, checked) => void patchMembership(membershipId, { [field]: checked })}
            onTelegramChange={(membershipId, value) => setTelegramDrafts((current) => ({ ...current, [membershipId]: value }))}
            onSaveTelegram={(membershipId) => void saveMembershipTelegram(membershipId)}
            onBitrixAllowChange={(membershipId, checked) => setBitrixAllowDrafts((current) => ({ ...current, [membershipId]: checked }))}
            onBitrixTelegramChange={(membershipId, value) => setBitrixTelegramDrafts((current) => ({ ...current, [membershipId]: value }))}
            onSaveBitrix={(membershipId) => void saveBitrixAccess(membershipId)}
            onToggleGroupMembership={(user, group, checked) => void toggleUserGroupMembership(user, group, checked)}
            onDeleteUser={(userId) => void deleteUser(userId)}
          />
        </div>
      ) : null}

      {activeTab === "groups" ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-4">
            <Panel tone="elevated" className="border-slate-200">
              <PanelHeader title="Группы" subtitle="Группы сотрудников используются в доступах и редакторских правах базы знаний." />
              <PanelBody className="space-y-4">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
                  <SearchInput value={groupsSearch} onChange={setGroupsSearch} placeholder="Поиск группы по названию" />
                  <SelectBox value={groupsUsage} onChange={setGroupsUsage} options={[["all", "Все группы"], ["filled", "С участниками"], ["empty", "Пустые"]]} />
                </div>
                <div className="space-y-3">
                  {loading ? <EmptyPanel title="Загружаю группы" body="Поднимаю группы сотрудников и их состав." /> : null}
                  {!loading && visibleGroups.length === 0 ? <EmptyPanel title="Группы не найдены" body="Подходящих групп сотрудников пока нет." /> : null}
                  {!loading && visibleGroups.map((group) => (
                    <button key={group.id} type="button" onClick={() => setGroupDrawer({ open: true, group, tab: "overview" })} className="grid w-full gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-3.5 text-left transition hover:border-sky-200 hover:bg-sky-50/40 lg:grid-cols-[minmax(0,1.2fr)_auto_110px]">
                      <div className="min-w-0">
                        <div className="truncate text-[15px] font-semibold text-slate-950">{group.name}</div>
                        <div className="mt-1 text-sm text-slate-500">Группа сотрудников для доступа и редакторских сценариев.</div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="sky">Сотрудники</Badge>
                        <Badge tone="neutral">Участников: {group.membership_ids.length}</Badge>
                      </div>
                      <div className="flex items-start justify-end"><Button size="sm" variant="ghost">Открыть</Button></div>
                    </button>
                  ))}
                </div>
              </PanelBody>
            </Panel>
          </div>
          <GroupInspector
            state={groupDrawer}
            allUsers={users}
            canManageSettings={canManageSettings}
            onOpenChange={(open) => setGroupDrawer((current) => ({ ...current, open }))}
            onTabChange={(tab) => setGroupDrawer((current) => ({ ...current, tab }))}
            onEditGroup={(group) => openEditGroupDialog(group)}
            onDeleteGroup={(groupId) => void deleteGroup(groupId)}
          />
        </div>
      ) : null}

      {activeTab === "defaults" ? (
        <Panel tone="elevated" className="border-slate-200">
          <PanelHeader title="Доступ по умолчанию" subtitle="Сейчас это не отдельный объект аккаунта, а настройки ролей плюс возможные персональные исключения." />
          <PanelBody className="grid gap-4 lg:grid-cols-3">
            <DefaultAccessCard title="Владелец" value="Управление доступом" description="Владелец аккаунта получает максимальный внутренний доступ по умолчанию." />
            <DefaultAccessCard title="Администратор" value="Редактирование" description="Администраторы по умолчанию могут изменять материалы и переиндексировать их без дополнительных правил." />
            <DefaultAccessCard title="Сотрудник" value="Чтение" description="Сотрудники по умолчанию получают чтение. Дальше папки базы знаний и персональные исключения могут это уточнять." />
            <div className="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm leading-6 text-slate-600 lg:col-span-3">Это честное отображение текущего серверного контракта. Сейчас отдельной сущности уровня аккаунта для базового доступа нет: используются настройки ролей и персональные значения доступа у конкретного сотрудника.</div>
            <div className="rounded-3xl border border-slate-200 bg-white px-5 py-5 lg:col-span-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Уровни прав базы знаний</div>
              <div className="mt-3 text-sm leading-6 text-slate-600">Внутренний контур теперь использует 4 уровня: чтение, загрузка, редактирование и управление доступом. Права папок в базе знаний уточняют этот базовый уровень.</div>
              <div className="mt-4">
                <PlannedPermissionLevels />
              </div>
            </div>
          </PanelBody>
        </Panel>
      ) : null}

      {activeTab === "invites" ? (
        <Panel tone="elevated" className="border-slate-200">
          <PanelHeader title="Приглашения" subtitle="Отдельный поток для ещё не активированных участников аккаунта." />
          <PanelBody className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_220px_auto]">
              <input className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700" placeholder="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} disabled={!canInviteUsers} />
              <SelectBox value={inviteRole} onChange={(value) => setInviteRole(value as InviteRole)} options={[["member", "Сотрудник"], ["admin", "Администратор"]]} disabled={!canInviteUsers} />
              <Button variant="primary" disabled={!canInviteUsers} onClick={() => void createInvite()}>Отправить</Button>
            </div>
            <div className="space-y-3">
              {loading ? <EmptyPanel title="Загружаю приглашения" body="Проверяю активные и отозванные приглашения." /> : null}
              {!loading && invites.length === 0 ? <EmptyPanel title="Приглашений пока нет" body="Ни одного приглашения ещё не отправлено." /> : null}
              {!loading && invites.map((invite) => (
                <div key={invite.id} className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-200 px-5 py-4">
                  <div className="min-w-0">
                    <div className="truncate text-base font-semibold text-slate-950">{invite.email || "Без email"}</div>
                    <div className="mt-1 text-sm text-slate-500">Роль: {roleLabel(invite.role as UsersAccessUserItem["role"])} · Статус: {statusLabel(invite.status)}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="secondary" disabled={!invite.accept_url} onClick={() => void copyInviteLink(invite.accept_url)}>Копировать ссылку</Button>
                    <Button size="sm" variant="danger" disabled={invite.status !== "pending" || !canInviteUsers} onClick={() => void revokeInvite(invite.id)}>Отозвать</Button>
                  </div>
                </div>
              ))}
            </div>
          </PanelBody>
        </Panel>
      ) : null}
    </div>
  );
}

function PeopleSummaryPanel(props: { staffUsersCount: number; adminUsersCount: number; telegramLinkedCount: number; bitrixLinkedCount: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <SummaryCard title="Сотрудники" value={props.staffUsersCount} body="Все внутренние пользователи аккаунта." />
      <SummaryCard title="Администраторы" value={props.adminUsersCount} body="Администраторы и владелец аккаунта." tone="amber" />
      <SummaryCard title="Telegram" value={props.telegramLinkedCount} body="Пользователи с привязкой Telegram." tone="amber" />
      <SummaryCard title="Bitrix" value={props.bitrixLinkedCount} body="Пользователи, связанные с Bitrix." tone="sky" />
    </div>
  );
}

function SummaryCard(props: { title: string; value: number; body: string; tone?: "default" | "sky" | "emerald" | "amber" }) {
  const toneClass = props.tone === "emerald" ? "border-emerald-200 bg-emerald-50/70" : props.tone === "amber" ? "border-amber-200 bg-amber-50/70" : props.tone === "sky" ? "border-sky-200 bg-sky-50/70" : "border-slate-200 bg-white";
  return <div className={`rounded-3xl border px-5 py-4 ${toneClass}`}><div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{props.title}</div><div className="mt-2 text-2xl font-semibold text-slate-950">{props.value}</div><div className="mt-1 text-sm text-slate-600">{props.body}</div></div>;
}

function DefaultAccessCard(props: { title: string; value: string; description: string }) {
  return <div className="rounded-3xl border border-slate-200 bg-white px-5 py-5"><div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{props.title}</div><div className="mt-3 text-2xl font-semibold text-slate-950">{props.value}</div><div className="mt-3 text-sm leading-6 text-slate-600">{props.description}</div></div>;
}

function PlannedPermissionLevels(props: { compact?: boolean }) {
  const levels = [
    { title: "Чтение", body: "Просмотр материалов." },
    { title: "Загрузка", body: "Добавление новых файлов." },
    { title: "Редактирование", body: "Замена файла, переиндексация, удаление и подпапки." },
    { title: "Управление доступом", body: "Настройка прав доступа и полный контроль над веткой." },
  ];
  return (
    <div className={`grid gap-3 ${props.compact ? "md:grid-cols-2" : "md:grid-cols-2 xl:grid-cols-4"}`}>
      {levels.map((level) => (
        <div key={level.title} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
          <div className="text-sm font-semibold text-slate-900">{level.title}</div>
          <div className="mt-2 text-sm leading-6 text-slate-600">{level.body}</div>
        </div>
      ))}
    </div>
  );
}

function EmptyPanel(props: { title: string; body: string }) {
  return <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50/80 px-5 py-5"><div className="text-base font-semibold text-slate-900">{props.title}</div><div className="mt-2 text-sm leading-6 text-slate-500">{props.body}</div></div>;
}

function UserInspector(props: {
  state: UserDrawerState;
  canInviteUsers: boolean;
  canManageSettings: boolean;
  telegramDrafts: Record<number, string>;
  bitrixAllowDrafts: Record<number, boolean>;
  bitrixTelegramDrafts: Record<number, string>;
  bitrixSavingMembershipId: number;
  savingMembershipId: number;
  savingGroupMembershipKey: string;
  groups: UsersAccessGroupItem[];
  onOpenChange: (open: boolean) => void;
  onTabChange: (tab: "overview" | "settings") => void;
  onRoleChange: (membershipId: number, role: UsersAccessUserItem["role"]) => void;
  onKbAccessChange: (membershipId: number, kbAccess: "none" | "read" | "upload" | "edit" | "manage") => void;
  onToggleFlag: (membershipId: number, field: "can_invite_users" | "can_manage_settings" | "can_view_finance", checked: boolean) => void;
  onTelegramChange: (membershipId: number, value: string) => void;
  onSaveTelegram: (membershipId: number) => void;
  onBitrixAllowChange: (membershipId: number, checked: boolean) => void;
  onBitrixTelegramChange: (membershipId: number, value: string) => void;
  onSaveBitrix: (membershipId: number) => void;
  onToggleGroupMembership: (user: UsersAccessUserItem, group: UsersAccessGroupItem, checked: boolean) => void;
  onDeleteUser: (userId: number) => void;
}) {
  const user = props.state.user;
  const editableGroups = useMemo(() => {
    if (!user) return [];
    return props.groups.filter((group) => group.kind === "staff");
  }, [props.groups, user]);
  return <InspectorPanel title={user ? user.display_name || "Без имени" : "Карточка пользователя"} subtitle={user ? `${roleLabel(user.role)} · ${statusLabel(user.status)}` : "Выбери человека в списке слева."} mode={props.state.tab} modes={[{ value: "overview", label: "Обзор" }, { value: "settings", label: "Настроить" }]} onModeChange={(value) => props.onTabChange(value as "overview" | "settings")} actions={user ? <Button size="sm" variant="ghost" onClick={() => props.onOpenChange(false)}>Закрыть</Button> : null}>
    {!user ? <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-5 py-7 text-sm leading-6 text-slate-500">Здесь появятся данные пользователя: каналы, группы, связь с базой знаний и доступы для настройки.</div> : null}
    {user && props.state.tab === "overview" ? <div className="space-y-4"><Section title="Каналы"><div className="flex flex-wrap gap-2">{renderIdentityBadges(user)}</div></Section><Section title="Группы"><div className="flex flex-wrap gap-2">{renderGroupBadges(user.groups)}</div></Section><Section title="Влияние на базу знаний"><div className="space-y-2 text-sm text-slate-600"><div>Базовый доступ: <span className="font-medium text-slate-900">{kbAccessLabel(user.permissions.kb_access)}</span></div><div>Группы сотрудников: <span className="font-medium text-slate-900">{Array.isArray(user.groups) && user.groups.length > 0 ? user.groups.map((group) => group.name).join(", ") : "нет"}</span></div><div>Папки базы знаний могут повысить или ограничить этот уровень через правила доступа и группы сотрудников.</div></div></Section></div> : null}
    {user && props.state.tab === "settings" ? (
      <div className="space-y-4 text-sm text-slate-600">
        <Section title="Роль и тип">
          <div className="grid gap-3">
            <SelectBox
              value={user.role}
              onChange={(value) => props.onRoleChange(user.membership_id, value as UsersAccessUserItem["role"])}
              options={[["owner", "Владелец"], ["admin", "Администратор"], ["member", "Сотрудник"]]}
              disabled={user.role === "owner" || !props.canManageSettings}
            />
            <SelectBox
              value={user.permissions.kb_access}
              onChange={(value) => props.onKbAccessChange(user.membership_id, value as "none" | "read" | "upload" | "edit" | "manage")}
              options={[["none", "Нет доступа"], ["read", "Чтение"], ["upload", "Загрузка"], ["edit", "Редактирование"], ["manage", "Управление доступом"]]}
              disabled={user.role === "owner" || !props.canManageSettings}
            />
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">Текущий серверный контракт</div>
              <div className="mt-2 text-sm leading-6 text-slate-600">Сейчас сервер уже хранит 4 уровня внутреннего доступа. Папки базы знаний могут дополнительно уточнять права через правила доступа и группы сотрудников.</div>
              <div className="mt-3">
                <PlannedPermissionLevels compact />
              </div>
            </div>
          </div>
        </Section>
        <Section title="Telegram и Bitrix">
          <div className="space-y-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">Telegram</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <input
                  className="min-w-[220px] flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                  placeholder="@username"
                  value={props.telegramDrafts[user.membership_id] || ""}
                  disabled={!props.canInviteUsers}
                  onChange={(event) => props.onTelegramChange(user.membership_id, event.target.value)}
                />
                <Button size="sm" variant="secondary" disabled={!props.canInviteUsers || props.savingMembershipId === user.membership_id} onClick={() => props.onSaveTelegram(user.membership_id)}>
                  {props.savingMembershipId === user.membership_id ? "Сохраняю..." : "Сохранить Telegram"}
                </Button>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">Bitrix</div>
              {!user.access_center?.bitrix_linked ? <div className="mt-2 text-sm leading-6 text-slate-600">Bitrix не привязан.</div> : null}
              {user.access_center?.bitrix_linked ? (
                <div className="mt-3 space-y-3">
                  <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3">
                    <input
                      type="checkbox"
                      className={CHECKBOX_CLASS}
                      checked={!!props.bitrixAllowDrafts[user.membership_id]}
                      disabled={!props.canManageSettings}
                      onChange={(event) => props.onBitrixAllowChange(user.membership_id, event.target.checked)}
                    />
                    <span>Разрешить доступ через список допуска Bitrix</span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <input
                      className="min-w-[220px] flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                      placeholder="@telegram для Bitrix"
                      value={props.bitrixTelegramDrafts[user.membership_id] || ""}
                      disabled={!props.canManageSettings}
                      onChange={(event) => props.onBitrixTelegramChange(user.membership_id, event.target.value)}
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!props.canManageSettings || props.bitrixSavingMembershipId === user.membership_id}
                      onClick={() => props.onSaveBitrix(user.membership_id)}
                    >
                      {props.bitrixSavingMembershipId === user.membership_id ? "Сохраняю..." : "Сохранить Bitrix"}
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </Section>
        <Section title="Административные права">
          <div className="space-y-3">
            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
              <input type="checkbox" className={CHECKBOX_CLASS} checked={!!user.permissions.can_invite_users} disabled={user.role === "owner" || !props.canManageSettings} onChange={(event) => props.onToggleFlag(user.membership_id, "can_invite_users", event.target.checked)} />
              <span>Может приглашать пользователей</span>
            </label>
            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
              <input type="checkbox" className={CHECKBOX_CLASS} checked={!!user.permissions.can_manage_settings} disabled={user.role === "owner" || !props.canManageSettings} onChange={(event) => props.onToggleFlag(user.membership_id, "can_manage_settings", event.target.checked)} />
              <span>Может управлять настройками</span>
            </label>
            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
              <input type="checkbox" className={CHECKBOX_CLASS} checked={!!user.permissions.can_view_finance} disabled={user.role === "owner" || !props.canManageSettings} onChange={(event) => props.onToggleFlag(user.membership_id, "can_view_finance", event.target.checked)} />
              <span>Может смотреть финансы</span>
            </label>
          </div>
        </Section>
        <Section title="Группы">
          <div className="space-y-3">
            {editableGroups.length === 0 ? <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">Подходящих групп для этого типа пользователя пока нет.</div> : null}
            {editableGroups.map((group) => {
              const checked = group.membership_ids.includes(user.membership_id);
              const saveKey = `${user.membership_id}:${group.id}`;
              return (
                <label key={group.id} className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
                  <input
                    type="checkbox"
                      className={CHECKBOX_CLASS}
                    checked={checked}
                    disabled={!props.canManageSettings || props.savingGroupMembershipKey === saveKey}
                    onChange={(event) => props.onToggleGroupMembership(user, group, event.target.checked)}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-slate-900">{group.name}</div>
                    <div className="text-xs text-slate-500">Группа сотрудников</div>
                  </div>
                  {props.savingGroupMembershipKey === saveKey ? <span className="text-xs text-slate-500">Сохраняю...</span> : null}
                </label>
              );
            })}
          </div>
        </Section>
        <Section title="Опасные действия">
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="danger" disabled={user.role === "owner" || !props.canManageSettings} onClick={() => props.onDeleteUser(user.user_id)}>Удалить пользователя</Button>
          </div>
        </Section>
      </div>
    ) : null}
  </InspectorPanel>;
}

function GroupInspector(props: {
  state: GroupDrawerState;
  allUsers: UsersAccessUserItem[];
  canManageSettings: boolean;
  onOpenChange: (open: boolean) => void;
  onTabChange: (tab: "overview" | "members") => void;
  onEditGroup: (group: UsersAccessGroupItem) => void;
  onDeleteGroup: (groupId: number) => void;
}) {
  const group = props.state.group;
  const members = useMemo(() => {
    if (!group) return [];
    const ids = new Set(group.membership_ids);
    return props.allUsers.filter((user) => ids.has(user.membership_id));
  }, [group, props.allUsers]);
  return <InspectorPanel title={group ? group.name : "Карточка группы"} subtitle={group ? `Группа сотрудников · ${group.membership_ids.length} участников` : "Выбери группу в списке слева."} mode={props.state.tab} modes={[{ value: "overview", label: "Обзор" }, { value: "members", label: "Участники" }]} onModeChange={(value) => props.onTabChange(value as "overview" | "members")} actions={group ? <div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" disabled={!props.canManageSettings} onClick={() => props.onEditGroup(group)}>Редактировать</Button><Button size="sm" variant="danger" disabled={!props.canManageSettings} onClick={() => props.onDeleteGroup(group.id)}>Удалить</Button><Button size="sm" variant="ghost" onClick={() => props.onOpenChange(false)}>Закрыть</Button></div> : null}>
    {!group ? <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-sm leading-6 text-slate-500">Здесь появятся состав группы и связь с базой знаний.</div> : null}
    {group && props.state.tab === "overview" ? <div className="space-y-5"><Section title="Тип"><div className="flex flex-wrap gap-2"><Badge tone="sky">Группа сотрудников</Badge></div></Section><Section title="Влияние на базу знаний"><div className="text-sm leading-6 text-slate-600">Эта группа уже участвует в правилах доступа сотрудников и может использоваться в редакторских правах на папках базы знаний.</div></Section></div> : null}
    {group && props.state.tab === "members" ? <div className="space-y-3">{members.length === 0 ? <EmptyPanel title="Участников нет" body="Эта группа пока пустая." /> : null}{members.map((member) => <div key={member.membership_id} className="rounded-2xl border border-slate-200 px-4 py-3"><div className="text-sm font-semibold text-slate-900">{member.display_name || "Без имени"}</div><div className="mt-1 text-xs text-slate-500">{member.web?.email || member.web?.login || "—"}</div></div>)}</div> : null}
  </InspectorPanel>;
}

function Section(props: { title: string; children: ReactNode }) {
  return <section className="space-y-2.5 border-t border-slate-100 pt-4 first:border-t-0 first:pt-0"><div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{props.title}</div>{props.children}</section>;
}

function SearchInput(props: { value: string; onChange: (value: string) => void; placeholder: string; className?: string }) {
  return <input className={`w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 ${props.className || ""}`.trim()} value={props.value} onChange={(event) => props.onChange(event.target.value)} placeholder={props.placeholder} />;
}

function SelectBox<T extends string | number>(props: { value: T; onChange: (value: T) => void; options: Array<[T, string]>; disabled?: boolean; }) {
  return <select className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 disabled:opacity-60" value={String(props.value)} disabled={props.disabled} onChange={(event) => props.onChange((typeof props.value === "number" ? Number(event.target.value) : event.target.value) as T)}>{props.options.map(([value, label]) => <option key={String(value)} value={String(value)}>{label}</option>)}</select>;
}

function HowItWorksDialog(props: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return <Dialog.Root open={props.open} onOpenChange={props.onOpenChange}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" /><Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(760px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]"><div className="flex items-start justify-between gap-4"><div><Dialog.Title className="text-2xl font-semibold text-slate-950">Как устроены пользователи и доступы</Dialog.Title><Dialog.Description className="mt-2 text-sm leading-6 text-slate-600">Этот раздел управляет только внутренним контуром: сотрудниками, группами сотрудников, Bitrix, Telegram и базовыми правами аккаунта.</Dialog.Description></div><Dialog.Close asChild><Button size="sm" variant="secondary">Закрыть</Button></Dialog.Close></div><div className="mt-6 grid gap-4 md:grid-cols-3"><div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4"><div className="text-sm font-semibold text-slate-900">Сотрудники</div><div className="mt-2 text-sm leading-6 text-slate-600">Здесь живут только внутренние пользователи аккаунта: владелец, администраторы и сотрудники.</div></div><div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4"><div className="text-sm font-semibold text-slate-900">Каналы</div><div className="mt-2 text-sm leading-6 text-slate-600">Bitrix и Telegram — это привязки сотрудника. Клиентский Telegram-бот настраивается отдельно в интеграциях.</div></div><div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4"><div className="text-sm font-semibold text-slate-900">База знаний</div><div className="mt-2 text-sm leading-6 text-slate-600">Группы сотрудников и базовый доступ влияют на внутренние права в базе знаний. Клиентский контур материалов настраивается в самой базе знаний.</div></div></div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

function CreateUserDialog(props: {
  state: CreateUserDialogState;
  onOpenChange: (open: boolean) => void;
  onChange: (patch: Partial<CreateUserDialogState>) => void;
  onSubmit: () => void;
}) {
  return (
    <Dialog.Root open={props.state.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(620px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-2xl font-semibold text-slate-950">Добавить сотрудника</Dialog.Title>
              <Dialog.Description className="mt-2 text-sm leading-6 text-slate-600">
                Сначала создаём внутреннего пользователя аккаунта. Привязки Telegram и Bitrix настраиваются уже в карточке сотрудника.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild><Button size="sm" variant="secondary">Закрыть</Button></Dialog.Close>
          </div>
          <div className="mt-6 grid gap-3">
            <input className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700" placeholder="Имя" value={props.state.displayName} onChange={(event) => props.onChange({ displayName: event.target.value })} />
            <div className="grid gap-3 md:grid-cols-2">
              <input className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700" placeholder="Логин" value={props.state.login} onChange={(event) => props.onChange({ login: event.target.value })} />
              <input className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700" placeholder="Email (опционально)" value={props.state.email} onChange={(event) => props.onChange({ email: event.target.value })} />
            </div>
            <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
              <SelectBox value={props.state.role} onChange={(value) => props.onChange({ role: value as "member" | "admin" })} options={[["member", "Сотрудник"], ["admin", "Администратор"]]} />
              <input className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700" placeholder="Пароль" type="password" value={props.state.password} onChange={(event) => props.onChange({ password: event.target.value })} />
            </div>
            {props.state.message ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{props.state.message}</div> : null}
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="secondary" onClick={() => props.onOpenChange(false)}>Отмена</Button>
            <Button size="sm" variant="primary" disabled={props.state.saving} onClick={props.onSubmit}>
              {props.state.saving ? "Создаю..." : "Создать сотрудника"}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function GroupDialog(props: {
  state: GroupDialogState;
  users: UsersAccessUserItem[];
  onOpenChange: (open: boolean) => void;
  onChange: (patch: Partial<GroupDialogState>) => void;
  onToggleMembership: (membershipId: number, checked: boolean) => void;
  onSubmit: () => void;
}) {
  const selectableUsers = props.users.filter((user) => user.role !== "client");
  return (
    <Dialog.Root open={props.state.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(760px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-2xl font-semibold text-slate-950">{props.state.mode === "create" ? "Создать группу" : "Редактировать группу"}</Dialog.Title>
              <Dialog.Description className="mt-2 text-sm leading-6 text-slate-600">
                Группы сотрудников — основная сущность для внутреннего доступа к базе знаний и редакторских сценариев.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild><Button size="sm" variant="secondary">Закрыть</Button></Dialog.Close>
          </div>
          <div className="mt-6 space-y-4">
            <input className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700" placeholder="Название группы" value={props.state.name} onChange={(event) => props.onChange({ name: event.target.value })} />
            <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Участники</div>
              <div className="mt-3 grid max-h-[320px] gap-2 overflow-auto pr-1">
                {selectableUsers.length === 0 ? <div className="text-sm text-slate-500">Нет подходящих сотрудников для этой группы.</div> : null}
                {selectableUsers.map((user) => (
                  <label key={user.membership_id} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3">
                    <input
                      type="checkbox"
                      className={CHECKBOX_CLASS}
                      checked={props.state.membershipIds.includes(user.membership_id)}
                      onChange={(event) => props.onToggleMembership(user.membership_id, event.target.checked)}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-slate-900">{user.display_name || "Без имени"}</div>
                      <div className="truncate text-xs text-slate-500">{user.web?.email || user.web?.login || "—"}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            {props.state.message ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{props.state.message}</div> : null}
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="secondary" onClick={() => props.onOpenChange(false)}>Отмена</Button>
            <Button size="sm" variant="primary" disabled={props.state.saving} onClick={props.onSubmit}>
              {props.state.saving ? "Сохраняю..." : props.state.mode === "create" ? "Создать группу" : "Сохранить группу"}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function renderIdentityBadges(user: UsersAccessUserItem) {
  const badges = [];
  if (user.web) badges.push(<Badge key="web" tone="neutral">Веб</Badge>);
  if (Array.isArray(user.bitrix) && user.bitrix.length > 0) badges.push(<Badge key="bitrix" tone="amber">Bitrix</Badge>);
  if (Array.isArray(user.telegram) && user.telegram.length > 0) badges.push(<Badge key="telegram" tone="sky">Telegram</Badge>);
  if (Array.isArray(user.amo) && user.amo.length > 0) badges.push(<Badge key="amo" tone="fuchsia">Amo</Badge>);
  return badges.length > 0 ? badges : [<Badge key="none" tone="neutral">Без каналов</Badge>];
}

function renderGroupBadges(groups: UsersAccessUserItem["groups"]) {
  if (!Array.isArray(groups) || groups.length === 0) return [<Badge key="none" tone="neutral">Без групп</Badge>];
  const staffGroups = groups.filter((group) => group.kind !== "client");
  const head = staffGroups.slice(0, 2).map((group) => <Badge key={group.id} tone="sky">{group.name}</Badge>);
  if (head.length === 0) return [<Badge key="none" tone="neutral">Без групп</Badge>];
  if (staffGroups.length > 2) head.push(<Badge key="more" tone="neutral">+{staffGroups.length - 2}</Badge>);
  return head;
}

function StatusBadge(props: { status: string }) {
  const tone = props.status === "active" ? "emerald" : props.status === "invited" ? "amber" : props.status === "blocked" ? "rose" : "neutral";
  return <Badge tone={tone}>{statusLabel(props.status)}</Badge>;
}

function roleLabel(role: string) {
  if (role === "owner") return "Владелец";
  if (role === "admin") return "Администратор";
  return "Сотрудник";
}

function statusLabel(status: string) {
  if (status === "active") return "Активен";
  if (status === "invited") return "Приглашён";
  if (status === "blocked") return "Заблокирован";
  if (status === "deleted") return "Удалён";
  return status || "—";
}

function kbAccessLabel(access: string) {
  if (access === "manage") return "Управление доступом";
  if (access === "edit") return "Редактирование";
  if (access === "upload") return "Загрузка";
  if (access === "read") return "Чтение";
  return "Нет доступа";
}

function buildTelegramDrafts(users: UsersAccessUserItem[]) {
  const drafts: Record<number, string> = {};
  for (const user of users) {
    const value =
      Array.isArray(user.telegram) && user.telegram.length > 0
        ? String(user.telegram[0]?.external_id || user.telegram[0]?.display_value || "").replace(/^@/, "")
        : user.access_center?.telegram_username || "";
    if (value) drafts[user.membership_id] = value;
  }
  return drafts;
}

function buildBitrixAccessState(users: UsersAccessUserItem[]) {
  const allowMap: Record<number, boolean> = {};
  const telegramMap: Record<number, string> = {};
  const selectedIds = new Set<number>();
  for (const user of users) {
    const linkedIds = (user.access_center?.bitrix_user_ids || []).map((value) => Number(value)).filter((value) => Number.isFinite(value));
    allowMap[user.membership_id] = !!user.access_center?.bitrix_allowlist;
    telegramMap[user.membership_id] = user.access_center?.telegram_username || "";
    if (user.access_center?.bitrix_allowlist) {
      linkedIds.forEach((id) => selectedIds.add(id));
    }
  }
  return {
    allowMap,
    telegramMap,
    selectedIds: Array.from(selectedIds),
  };
}
