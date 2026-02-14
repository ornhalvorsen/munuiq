import { fetchJSON } from "@/lib/api-client";
import type { MentionEntity } from "@/components/mentions/types";

interface LookupsResponse {
  locations: Array<{ id: string; label: string; description?: string | null }>;
  products: Array<{ id: string; label: string; description?: string | null }>;
}

let _cache: Record<string, MentionEntity[]> | null = null;

export async function fetchLookups(): Promise<
  Record<string, MentionEntity[]>
> {
  if (_cache) return _cache;

  const data = await fetchJSON<LookupsResponse>("/lookups");

  _cache = {
    location: data.locations.map((l) => ({
      id: l.id,
      label: l.label,
      description: l.description ?? undefined,
      type: "location",
    })),
    product: data.products.map((p) => ({
      id: p.id,
      label: p.label,
      description: p.description ?? undefined,
      type: "product",
    })),
  };

  return _cache;
}

export function invalidateLookups(): void {
  _cache = null;
}
