"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getOnboardingStatus,
  startOnboarding,
  OnboardingStatus,
} from "@/lib/api/onboarding";
import { Rocket, ArrowRight } from "lucide-react";

export default function OnboardingListPage() {
  const { user } = useAuth();
  const { customerList } = useTenant();
  const router = useRouter();
  const [statuses, setStatuses] = useState<
    Record<number, OnboardingStatus | null>
  >({});
  const [loading, setLoading] = useState(true);

  // For superadmins, show all tenants' customers. For others, show their list.
  const customerIds =
    user?.role === "superadmin" ? customerList : user?.customer_ids || [];

  useEffect(() => {
    async function loadStatuses() {
      const results: Record<number, OnboardingStatus | null> = {};
      for (const id of customerIds) {
        try {
          results[id] = await getOnboardingStatus(id);
        } catch {
          results[id] = null;
        }
      }
      setStatuses(results);
      setLoading(false);
    }
    if (customerIds.length > 0) {
      loadStatuses();
    } else {
      setLoading(false);
    }
  }, [customerIds.join(",")]);

  async function handleStart(customerId: number) {
    await startOnboarding(customerId);
    router.push(`/onboarding/${customerId}/entities`);
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Rocket className="h-6 w-6" />
        <h1 className="text-2xl font-semibold">Onboarding</h1>
      </div>
      <p className="text-muted-foreground">
        Set up new customers by mapping their locations, categories, and
        products.
      </p>

      {customerIds.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No customers assigned. Contact your administrator.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {customerIds.map((id) => {
            const status = statuses[id];
            const started = status?.started;
            return (
              <Card key={id}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-base">
                    Customer {id}
                    {started ? (
                      <Badge variant="secondary">
                        {status?.current_step || "In progress"}
                      </Badge>
                    ) : (
                      <Badge variant="outline">Not started</Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {started ? (
                    <div className="space-y-2">
                      <p className="text-sm text-muted-foreground">
                        Steps completed:{" "}
                        {status?.completed_steps?.join(", ") || "None"}
                      </p>
                      <Button
                        size="sm"
                        onClick={() =>
                          router.push(
                            `/onboarding/${id}/${status?.current_step || "entities"}`
                          )
                        }
                      >
                        Continue
                        <ArrowRight className="ml-1 h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <Button size="sm" onClick={() => handleStart(id)}>
                      Start onboarding
                      <ArrowRight className="ml-1 h-3 w-3" />
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
