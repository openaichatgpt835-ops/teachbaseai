export type KbV2File = {
  id: number;
  filename: string;
  folder_id?: number | null;
  status: string;
  uploaded_by_name?: string;
  created_at?: string;
  access_badges?: { staff?: string; client?: string };
};

export type KbV2Folder = {
  id: number;
  name: string;
  parent_id?: number | null;
  created_at?: string | null;
  access_badges?: { staff?: string; client?: string };
};

export type KbV2AclItem = {
  principal_type: string;
  principal_id: string;
  access_level: string;
};

export type KbV2AccessSummary = {
  total_ready_files: number;
  open_all_clients: number;
  open_client_groups: number;
  closed_for_clients: number;
};

export type KbV2Selection =
  | { kind: "folder"; id: number }
  | { kind: "file"; id: number }
  | null;
