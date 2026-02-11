"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Check, X } from "lucide-react";
import { Mapping, MappingUpdate } from "@/lib/api/onboarding";

interface ProductGroupingProps {
  mappings: Mapping[];
  onUpdate: (updates: MappingUpdate[]) => void;
  loading?: boolean;
}

export function ProductGrouping({
  mappings,
  onUpdate,
  loading,
}: ProductGroupingProps) {
  const [localMappings, setLocalMappings] = useState(mappings);
  const [pendingUpdates, setPendingUpdates] = useState<MappingUpdate[]>([]);

  // Group by base_product
  const grouped = localMappings.reduce(
    (acc, m) => {
      let parsed: { base_product: string; product_type: string };
      try {
        parsed = JSON.parse(m.proposed_value);
      } catch {
        parsed = { base_product: "Unknown", product_type: "regular" };
      }
      const key = parsed.base_product;
      if (!acc[key]) acc[key] = [];
      acc[key].push({ ...m, _parsed: parsed });
      return acc;
    },
    {} as Record<
      string,
      (Mapping & { _parsed: { base_product: string; product_type: string } })[]
    >
  );

  function approveGroup(groupName: string) {
    const ids = grouped[groupName]
      .filter((m) => m.status === "proposed")
      .map((m) => m.id);
    const updates = ids.map((id) => ({
      id,
      status: "approved" as const,
    }));
    setPendingUpdates((prev) => {
      const idSet = new Set(ids);
      return [...prev.filter((u) => !idSet.has(u.id)), ...updates];
    });
    setLocalMappings((prev) =>
      prev.map((m) =>
        ids.includes(m.id) ? { ...m, status: "approved" } : m
      )
    );
  }

  function rejectItem(id: number) {
    setPendingUpdates((prev) => [
      ...prev.filter((u) => u.id !== id),
      { id, status: "rejected" },
    ]);
    setLocalMappings((prev) =>
      prev.map((m) => (m.id === id ? { ...m, status: "rejected" } : m))
    );
  }

  function submitAll() {
    if (pendingUpdates.length > 0) onUpdate(pendingUpdates);
  }

  const pendingCount = localMappings.filter(
    (m) => m.status === "proposed"
  ).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Review product variant groupings. Approve groups or reject individual
          items.
        </p>
        <Button
          size="sm"
          onClick={submitAll}
          disabled={loading || pendingUpdates.length === 0}
        >
          {loading ? "Saving..." : `Save changes (${pendingUpdates.length})`}
        </Button>
      </div>

      <div className="space-y-3">
        {Object.entries(grouped).map(([groupName, items]) => {
          const allApproved = items.every((m) => m.status !== "proposed");
          return (
            <Card key={groupName}>
              <CardContent className="pt-4">
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="font-medium">{groupName}</h4>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                      {items.length} items
                    </Badge>
                    {!allApproved && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => approveGroup(groupName)}
                      >
                        <Check className="mr-1 h-3 w-3" />
                        Approve group
                      </Button>
                    )}
                  </div>
                </div>
                <div className="space-y-1">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-md px-2 py-1 text-sm hover:bg-muted/50"
                    >
                      <div className="flex items-center gap-2">
                        <span>{item.source_label || item.source_key}</span>
                        <Badge variant="outline" className="text-xs">
                          {item._parsed.product_type}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <Badge
                          variant={
                            item.status === "approved"
                              ? "default"
                              : item.status === "rejected"
                                ? "destructive"
                                : "outline"
                          }
                          className="text-xs"
                        >
                          {item.status}
                        </Badge>
                        {item.status === "proposed" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 text-red-600"
                            onClick={() => rejectItem(item.id)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {pendingCount === 0 && localMappings.length > 0 && (
        <p className="text-center text-sm text-muted-foreground">
          All product groupings have been reviewed.
        </p>
      )}
    </div>
  );
}
