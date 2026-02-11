"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CategoryMapping } from "@/components/onboarding/category-mapping";
import {
  proposeCategories,
  getCategories,
  updateCategories,
  Mapping,
  MappingUpdate,
} from "@/lib/api/onboarding";
import { Sparkles } from "lucide-react";

export default function CategoriesPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = Number(params.customerId);
  const [mappings, setMappings] = useState<Mapping[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [proposing, setProposing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getCategories(customerId)
      .then((resp) => {
        setMappings(resp.mappings.length > 0 ? resp.mappings : null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [customerId]);

  async function handlePropose() {
    setProposing(true);
    try {
      const resp = await proposeCategories(customerId);
      setMappings(resp.mappings);
    } catch (err) {
      console.error(err);
    } finally {
      setProposing(false);
    }
  }

  async function handleUpdate(updates: MappingUpdate[]) {
    setSaving(true);
    try {
      const resp = await updateCategories(customerId, updates);
      if (resp.pending === 0) {
        router.push(`/onboarding/${customerId}/products`);
      } else {
        // Refresh
        const fresh = await getCategories(customerId);
        setMappings(fresh.mappings);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!mappings) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-medium">Step 2: Category Mapping</h2>
        <p className="text-sm text-muted-foreground">
          Use AI to propose category mappings for this customer&apos;s article
          groups.
        </p>
        {proposing ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <p className="text-sm text-muted-foreground">
              Generating category proposals... This may take a moment.
            </p>
          </div>
        ) : (
          <Button onClick={handlePropose}>
            <Sparkles className="mr-2 h-4 w-4" />
            Generate category proposals
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium">Step 2: Review Categories</h2>
      <CategoryMapping
        mappings={mappings}
        onUpdate={handleUpdate}
        loading={saving}
      />
    </div>
  );
}
