export interface Portal {
  id: number;
  domain: string;
  status: string;
}

export interface Dialog {
  id: number;
  portal_id: number;
  provider_dialog_id: string;
}
