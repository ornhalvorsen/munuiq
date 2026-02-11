"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getIntegrations,
  mapIntegration,
  scanEntities,
  Installation,
} from "@/lib/api/onboarding";
import { ArrowRight, Link2 } from "lucide-react";

interface Department {
  department_id: number;
  department_name: string;
  matched_installation_id: number | null;
  matched_installation_name: string | null;
  match_confidence: number;
}

export default function IntegrationsPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = Number(params.customerId);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [installations, setInstallations] = useState<Installation[]>([]);
  const [loading, setLoading] = useState(true);
  const [mappings, setMappings] = useState<Record<number, number>>({});

  useEffect(() => {
    async function load() {
      try {
        const [intData, entityData] = await Promise.all([
          getIntegrations(customerId) as Promise<{
            planday: Department[];
            cakeiteasy: unknown[];
          }>,
          scanEntities(customerId),
        ]);
        setDepartments(intData.planday || []);
        setInstallations(entityData.installations || []);

        // Pre-fill from auto-matches
        const initial: Record<number, number> = {};
        for (const d of intData.planday || []) {
          if (d.matched_installation_id) {
            initial[d.department_id] = d.matched_installation_id;
          }
        }
        setMappings(initial);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [customerId]);

  async function handleSaveAll() {
    for (const [deptId, instId] of Object.entries(mappings)) {
      await mapIntegration(customerId, Number(deptId), instId);
    }
    router.push(`/onboarding/${customerId}/validation`);
  }

  if (loading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (departments.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-medium">Step 4: Integrations</h2>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No Planday departments found for this customer. You can skip this
            step.
          </CardContent>
        </Card>
        <div className="flex justify-end">
          <Button
            onClick={() =>
              router.push(`/onboarding/${customerId}/validation`)
            }
          >
            Skip to validation
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium">Step 4: Integration Mapping</h2>
      <p className="text-sm text-muted-foreground">
        Map Planday departments to their corresponding installations.
      </p>
      <div className="space-y-3">
        {departments.map((dept) => (
          <Card key={dept.department_id}>
            <CardContent className="flex items-center justify-between pt-4">
              <div className="flex items-center gap-3">
                <Link2 className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">
                    {dept.department_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Planday Dept #{dept.department_id}
                  </p>
                </div>
                {dept.match_confidence > 0.5 && (
                  <Badge variant="secondary" className="text-xs">
                    Auto-matched ({(dept.match_confidence * 100).toFixed(0)}%)
                  </Badge>
                )}
              </div>
              <Select
                value={mappings[dept.department_id]?.toString() || ""}
                onValueChange={(v) =>
                  setMappings((prev) => ({
                    ...prev,
                    [dept.department_id]: Number(v),
                  }))
                }
              >
                <SelectTrigger className="w-64">
                  <SelectValue placeholder="Select installation" />
                </SelectTrigger>
                <SelectContent>
                  {installations.map((inst) => (
                    <SelectItem
                      key={inst.installation_id}
                      value={inst.installation_id.toString()}
                    >
                      {inst.display_name || inst.installation_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="flex justify-end">
        <Button onClick={handleSaveAll}>
          Save & continue
          <ArrowRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
