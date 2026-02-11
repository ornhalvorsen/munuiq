import { fetchJSON } from "@/lib/api-client";

export interface OnboardingStatus {
  started: boolean;
  current_step: string | null;
  completed_steps: string[];
  started_at?: string;
  updated_at?: string;
}

export interface EntityScanResult {
  business_units: Record<string, unknown>[];
  installations: Installation[];
  revenue_units: Record<string, unknown>[];
}

export interface Installation {
  installation_id: number;
  installation_name: string;
  address?: string;
  display_name: string;
  entity_type: string;
  selected: boolean;
}

export interface Mapping {
  id: number;
  customer_id: number;
  mapping_type: string;
  source_key: string;
  source_label: string;
  proposed_value: string;
  confidence: number;
  status: string;
  final_value: string | null;
  approved_by: number | null;
}

export interface MappingUpdate {
  id: number;
  status: "approved" | "rejected" | "modified";
  final_value?: string;
}

export interface OnboardingSummary {
  categories: { total: number; approved: number; rejected: number; pending: number };
  products: { total: number; approved: number; rejected: number; pending: number };
  warnings: string[];
  ready: boolean;
}

export function getOnboardingStatus(customerId: number) {
  return fetchJSON<OnboardingStatus>(`/onboarding/${customerId}/status`);
}

export function startOnboarding(customerId: number) {
  return fetchJSON(`/onboarding/${customerId}/start`, { method: "POST" });
}

export function scanEntities(customerId: number) {
  return fetchJSON<EntityScanResult>(`/onboarding/${customerId}/entities/scan`, {
    method: "POST",
  });
}

export function confirmEntities(
  customerId: number,
  installations: Installation[]
) {
  return fetchJSON(`/onboarding/${customerId}/entities/confirm`, {
    method: "POST",
    body: JSON.stringify({ installations }),
  });
}

export function proposeCategories(customerId: number) {
  return fetchJSON<{ mappings: Mapping[]; count: number }>(
    `/onboarding/${customerId}/categories/propose`,
    { method: "POST" }
  );
}

export function getCategories(customerId: number) {
  return fetchJSON<{ mappings: Mapping[]; count: number }>(
    `/onboarding/${customerId}/categories`
  );
}

export function updateCategories(
  customerId: number,
  updates: MappingUpdate[]
) {
  return fetchJSON<{ updated: number; pending: number }>(
    `/onboarding/${customerId}/categories`,
    { method: "PATCH", body: JSON.stringify({ updates }) }
  );
}

export function proposeProducts(customerId: number) {
  return fetchJSON<{ mappings: Mapping[]; count: number }>(
    `/onboarding/${customerId}/products/propose`,
    { method: "POST" }
  );
}

export function getProducts(customerId: number) {
  return fetchJSON<{ mappings: Mapping[]; count: number }>(
    `/onboarding/${customerId}/products`
  );
}

export function updateProducts(
  customerId: number,
  updates: MappingUpdate[]
) {
  return fetchJSON<{ updated: number; pending: number }>(
    `/onboarding/${customerId}/products`,
    { method: "PATCH", body: JSON.stringify({ updates }) }
  );
}

export function getIntegrations(customerId: number) {
  return fetchJSON(`/onboarding/${customerId}/integrations`);
}

export function mapIntegration(
  customerId: number,
  departmentId: number,
  installationId: number
) {
  return fetchJSON(
    `/onboarding/${customerId}/integrations/${departmentId}/map`,
    {
      method: "POST",
      body: JSON.stringify({
        department_id: departmentId,
        installation_id: installationId,
      }),
    }
  );
}

export function getOnboardingSummary(customerId: number) {
  return fetchJSON<OnboardingSummary>(`/onboarding/${customerId}/summary`);
}

export function approveOnboarding(customerId: number) {
  return fetchJSON(`/onboarding/${customerId}/approve`, { method: "POST" });
}
