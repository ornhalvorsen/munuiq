"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Check, X, Pencil } from "lucide-react";
import { Mapping, MappingUpdate } from "@/lib/api/onboarding";

interface CategoryMappingProps {
  mappings: Mapping[];
  onUpdate: (updates: MappingUpdate[]) => void;
  loading?: boolean;
}

export function CategoryMapping({
  mappings,
  onUpdate,
  loading,
}: CategoryMappingProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  const [localMappings, setLocalMappings] = useState(mappings);
  const [pendingUpdates, setPendingUpdates] = useState<MappingUpdate[]>([]);

  function startEdit(m: Mapping) {
    setEditingId(m.id);
    setEditValue(m.proposed_value);
  }

  function saveEdit(id: number) {
    const update: MappingUpdate = {
      id,
      status: "modified",
      final_value: editValue,
    };
    setPendingUpdates((prev) => [
      ...prev.filter((u) => u.id !== id),
      update,
    ]);
    setLocalMappings((prev) =>
      prev.map((m) =>
        m.id === id
          ? { ...m, status: "modified", final_value: editValue }
          : m
      )
    );
    setEditingId(null);
  }

  function approve(id: number) {
    const update: MappingUpdate = { id, status: "approved" };
    setPendingUpdates((prev) => [
      ...prev.filter((u) => u.id !== id),
      update,
    ]);
    setLocalMappings((prev) =>
      prev.map((m) => (m.id === id ? { ...m, status: "approved" } : m))
    );
  }

  function reject(id: number) {
    const update: MappingUpdate = { id, status: "rejected" };
    setPendingUpdates((prev) => [
      ...prev.filter((u) => u.id !== id),
      update,
    ]);
    setLocalMappings((prev) =>
      prev.map((m) => (m.id === id ? { ...m, status: "rejected" } : m))
    );
  }

  function approveAll() {
    const updates = localMappings
      .filter((m) => m.status === "proposed")
      .map((m) => ({ id: m.id, status: "approved" as const }));
    setPendingUpdates((prev) => {
      const ids = new Set(updates.map((u) => u.id));
      return [...prev.filter((u) => !ids.has(u.id)), ...updates];
    });
    setLocalMappings((prev) =>
      prev.map((m) =>
        m.status === "proposed" ? { ...m, status: "approved" } : m
      )
    );
  }

  function submitAll() {
    if (pendingUpdates.length > 0) {
      onUpdate(pendingUpdates);
    }
  }

  const pendingCount = localMappings.filter(
    (m) => m.status === "proposed"
  ).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Review proposed category mappings. Accept, reject, or edit each one.
        </p>
        <div className="flex gap-2">
          {pendingCount > 0 && (
            <Button variant="outline" size="sm" onClick={approveAll}>
              Approve all ({pendingCount})
            </Button>
          )}
          <Button
            size="sm"
            onClick={submitAll}
            disabled={loading || pendingUpdates.length === 0}
          >
            {loading
              ? "Saving..."
              : `Save changes (${pendingUpdates.length})`}
          </Button>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source Group</TableHead>
              <TableHead>Proposed Category</TableHead>
              <TableHead className="w-24">Confidence</TableHead>
              <TableHead className="w-24">Status</TableHead>
              <TableHead className="w-32">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {localMappings.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="text-sm">
                  {m.source_label || m.source_key}
                </TableCell>
                <TableCell>
                  {editingId === m.id ? (
                    <div className="flex items-center gap-1">
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="h-7 text-sm"
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => saveEdit(m.id)}
                      >
                        <Check className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <span className="text-sm">
                      {m.final_value || m.proposed_value}
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      m.confidence >= 0.9
                        ? "default"
                        : m.confidence >= 0.7
                          ? "secondary"
                          : "outline"
                    }
                    className="text-xs"
                  >
                    {(m.confidence * 100).toFixed(0)}%
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      m.status === "approved"
                        ? "default"
                        : m.status === "rejected"
                          ? "destructive"
                          : m.status === "modified"
                            ? "secondary"
                            : "outline"
                    }
                    className="text-xs"
                  >
                    {m.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  {m.status === "proposed" && (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-green-600"
                        onClick={() => approve(m.id)}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-600"
                        onClick={() => reject(m.id)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => startEdit(m)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
