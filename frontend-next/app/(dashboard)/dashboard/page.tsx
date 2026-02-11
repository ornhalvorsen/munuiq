"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/components/analytics/data-table";
import { InsightChart } from "@/components/analytics/insight-chart";
import { getDashboard, DashboardCard } from "@/lib/api/analytics";

export default function DashboardPage() {
  const [cards, setCards] = useState<DashboardCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [cached, setCached] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then((resp) => {
        setCards(resp.cards);
        setCached(resp.cached);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-40" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-40 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        {cached && (
          <Badge variant="secondary">Cached (10 min TTL)</Badge>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {cards.map((card, i) => (
          <Card key={i}>
            <CardHeader>
              <CardTitle className="text-base">{card.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">{card.insight}</p>
              <InsightChart
                chart={card.chart}
                columns={card.columns}
                data={card.data}
              />
              <DataTable
                columns={card.columns}
                data={card.data}
                maxRows={10}
              />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
