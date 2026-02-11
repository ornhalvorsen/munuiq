"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductGrouping } from "@/components/onboarding/product-grouping";
import {
  proposeProducts,
  getProducts,
  updateProducts,
  Mapping,
  MappingUpdate,
} from "@/lib/api/onboarding";
import { Sparkles } from "lucide-react";

export default function ProductsPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = Number(params.customerId);
  const [mappings, setMappings] = useState<Mapping[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [proposing, setProposing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getProducts(customerId)
      .then((resp) => {
        setMappings(resp.mappings.length > 0 ? resp.mappings : null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [customerId]);

  async function handlePropose() {
    setProposing(true);
    try {
      const resp = await proposeProducts(customerId);
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
      const resp = await updateProducts(customerId, updates);
      if (resp.pending === 0) {
        router.push(`/onboarding/${customerId}/integrations`);
      } else {
        const fresh = await getProducts(customerId);
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
        <h2 className="text-lg font-medium">Step 3: Product Grouping</h2>
        <p className="text-sm text-muted-foreground">
          Use AI to group product variants, identify deals, and flag test items.
        </p>
        {proposing ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <p className="text-sm text-muted-foreground">
              Analyzing products... This may take a moment.
            </p>
          </div>
        ) : (
          <Button onClick={handlePropose}>
            <Sparkles className="mr-2 h-4 w-4" />
            Generate product groupings
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium">Step 3: Review Products</h2>
      <ProductGrouping
        mappings={mappings}
        onUpdate={handleUpdate}
        loading={saving}
      />
    </div>
  );
}
