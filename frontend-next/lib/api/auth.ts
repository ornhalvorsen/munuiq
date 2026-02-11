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

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  // Post to Next.js API route which proxies to FastAPI and sets cookie
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(body.detail || "Login failed");
  }
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

export async function getMe(): Promise<UserInfo> {
  return fetchJSON<UserInfo>("/auth/me");
}
