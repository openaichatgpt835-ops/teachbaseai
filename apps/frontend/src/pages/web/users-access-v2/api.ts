import { fetchWeb } from "../auth";
import type {
  UsersAccessCenterResponse,
  UsersAccessInviteItem,
  UsersAccessMeContext,
} from "./types";

export async function fetchUsersAccessMe(): Promise<UsersAccessMeContext | null> {
  const res = await fetchWeb("/api/v2/web/auth/me");
  if (!res.ok) return null;
  return res.json().catch(() => null);
}

export async function fetchUsersAccessCenter(accountId: number): Promise<UsersAccessCenterResponse | null> {
  const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/access-center`);
  if (!res.ok) return null;
  return res.json().catch(() => null);
}

export async function fetchUsersAccessInvites(accountId: number): Promise<UsersAccessInviteItem[]> {
  const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/invites`);
  const data = await res.json().catch(() => null);
  if (!res.ok) return [];
  return Array.isArray(data?.items) ? data.items : [];
}
