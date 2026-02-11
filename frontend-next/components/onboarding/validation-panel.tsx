"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { OnboardingSummary } from "@/lib/api/onboarding";

interface ValidationPanelProps {
  summary: OnboardingSummary;
  onApprove: () => void;
  loading?: boolean;
}

export function ValidationPanel({
  summary,
  onApprove,
  loading,
}: ValidationPanelProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Categories</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Total</span>
              <Badge variant="secondary">{summary.categories.total}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-green-600">Approved</span>
              <Badge>{summary.categories.approved}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-red-600">Rejected</span>
              <Badge variant="destructive">
                {summary.categories.rejected}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-yellow-600">Pending</span>
              <Badge variant="outline">{summary.categories.pending}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Products</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Total</span>
              <Badge variant="secondary">{summary.products.total}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-green-600">Approved</span>
              <Badge>{summary.products.approved}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-red-600">Rejected</span>
              <Badge variant="destructive">
                {summary.products.rejected}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-yellow-600">Pending</span>
              <Badge variant="outline">{summary.products.pending}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {summary.warnings.length > 0 && (
        <div className="space-y-2">
          {summary.warnings.map((w, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {w}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between rounded-md border p-4">
        <div className="flex items-center gap-2">
          {summary.ready ? (
            <>
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <span className="font-medium text-green-600">
                Ready for approval
              </span>
            </>
          ) : (
            <>
              <XCircle className="h-5 w-5 text-muted-foreground" />
              <span className="text-muted-foreground">
                Review all pending items before approving
              </span>
            </>
          )}
        </div>
        <Button
          onClick={onApprove}
          disabled={!summary.ready || loading}
          size="lg"
        >
          {loading ? "Approving..." : "Approve & Write to Production"}
        </Button>
      </div>
    </div>
  );
}
