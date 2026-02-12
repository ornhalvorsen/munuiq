import { fetchJSON } from "@/lib/api-client";

export interface UserInfo {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  customer_ids: number[];
  tenant_id: number | null;
  tenant_name: string | null;
}

export async function getMe(): Promise<UserInfo> {
  return fetchJSON<UserInfo>("/auth/me");
}
