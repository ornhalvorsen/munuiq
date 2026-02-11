"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { ValidationPanel } from "@/components/onboarding/validation-panel";
import {
  getOnboardingSummary,
  approveOnboarding,
  OnboardingSummary,
} from "@/lib/api/onboarding";

export default function ValidationPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = Number(params.customerId);
  const [summary, setSummary] = useState<OnboardingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);

  useEffect(() => {
    getOnboardingSummary(customerId)
      .then(setSummary)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [customerId]);

  async function handleApprove() {
    setApproving(true);
    try {
      await approveOnboarding(customerId);
      router.push("/onboarding");
    } catch (err) {
      console.error(err);
    } finally {
      setApproving(false);
    }
  }

  if (loading || !summary) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium">Step 5: Validation & Approval</h2>
      <ValidationPanel
        summary={summary}
        onApprove={handleApprove}
        loading={approving}
      />
    </div>
  );
}
