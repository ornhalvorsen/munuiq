"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EntityDiscovery } from "@/components/onboarding/entity-discovery";
import {
  scanEntities,
  confirmEntities,
  Installation,
} from "@/lib/api/onboarding";
import { Search } from "lucide-react";

export default function EntitiesPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = Number(params.customerId);
  const [installations, setInstallations] = useState<Installation[] | null>(
    null
  );
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);

  async function handleScan() {
    setScanning(true);
    try {
      const result = await scanEntities(customerId);
      setInstallations(result.installations);
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  }

  async function handleConfirm(items: Installation[]) {
    setSaving(true);
    try {
      await confirmEntities(customerId, items);
      router.push(`/onboarding/${customerId}/categories`);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  if (!installations) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-medium">Step 1: Discover Entities</h2>
        <p className="text-sm text-muted-foreground">
          Scan the database to discover locations, business units, and revenue
          units for this customer.
        </p>
        {scanning ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <Button onClick={handleScan}>
            <Search className="mr-2 h-4 w-4" />
            Scan for entities
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium">Step 1: Review Entities</h2>
      <EntityDiscovery
        installations={installations}
        onConfirm={handleConfirm}
        loading={saving}
      />
    </div>
  );
}
