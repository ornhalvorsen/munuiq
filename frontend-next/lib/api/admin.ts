import { fetchJSON } from "@/lib/api-client";

export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  tenant_id: number | null;
  tenant_name: string | null;
  created_at?: string;
}

export interface Tenant {
  id: number;
  name: string;
  customer_ids: number[];
  settings: Record<string, unknown>;
  is_active: boolean;
  users: { id: number; email: string; name: string; role: string }[];
  created_at?: string;
}

export function listUsers() {
  return fetchJSON<User[]>("/admin/users");
}

export function createUser(data: {
  email: string;
  password: string;
  name: string;
  role?: string;
}) {
  return fetchJSON("/admin/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateUser(
  userId: number,
  data: Partial<{ email: string; name: string; role: string; is_active: boolean }>
) {
  return fetchJSON(`/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteUser(userId: number) {
  return fetchJSON(`/admin/users/${userId}`, { method: "DELETE" });
}

export function listTenants() {
  return fetchJSON<Tenant[]>("/admin/tenants");
}

export function createTenant(data: {
  name: string;
  customer_ids: number[];
  settings?: Record<string, unknown>;
}) {
  return fetchJSON("/admin/tenants", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateTenant(
  tenantId: number,
  data: Partial<{
    name: string;
    customer_ids: number[];
    settings: Record<string, unknown>;
    is_active: boolean;
  }>
) {
  return fetchJSON(`/admin/tenants/${tenantId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteTenant(tenantId: number) {
  return fetchJSON(`/admin/tenants/${tenantId}`, { method: "DELETE" });
}

export function assignTenant(userId: number, tenantId: number) {
  return fetchJSON("/admin/assign-tenant", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, tenant_id: tenantId }),
  });
}
