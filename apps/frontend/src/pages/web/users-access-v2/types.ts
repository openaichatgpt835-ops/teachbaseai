export type LinkedIdentity = {
  id: number;
  external_id?: string | null;
  display_value?: string | null;
  integration_id?: number | null;
};

export type UsersAccessGroupItem = {
  id: number;
  name: string;
  kind: "staff" | "client";
  membership_ids: number[];
  members?: { membership_id: number; user_id: number; role: string; status: string }[];
};

export type UsersAccessUserItem = {
  membership_id: number;
  user_id: number;
  display_name?: string | null;
  role: "owner" | "admin" | "member" | "client";
  status: "active" | "invited" | "blocked" | "deleted";
  permissions: {
    kb_access: "none" | "read" | "upload" | "edit" | "manage";
    can_invite_users: boolean;
    can_manage_settings: boolean;
    can_view_finance: boolean;
  };
  web?: { login?: string | null; email?: string | null } | null;
  bitrix?: LinkedIdentity[];
  telegram?: LinkedIdentity[];
  amo?: LinkedIdentity[];
  access_center?: {
    portal_id?: number | null;
    bitrix_linked?: boolean;
    bitrix_allowlist?: boolean;
    bitrix_user_ids?: string[];
    telegram_username?: string | null;
  } | null;
  groups?: { id: number; name: string; kind?: "staff" | "client" }[];
};

export type UsersAccessInviteItem = {
  id: number;
  email?: string | null;
  role: string;
  status: string;
  expires_at?: string | null;
  created_at?: string | null;
  accepted_at?: string | null;
  accept_url?: string | null;
};

export type UsersAccessMeContext = {
  account?: { id?: number | null } | null;
  membership?: {
    role?: "owner" | "admin" | "member" | "client";
    kb_access?: "none" | "read" | "upload" | "edit" | "manage";
    can_invite_users?: boolean;
    can_manage_settings?: boolean;
    can_view_finance?: boolean;
  } | null;
};

export type UsersAccessCenterResponse = {
  items?: UsersAccessUserItem[];
  groups?: UsersAccessGroupItem[];
};
