"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Installation } from "@/lib/api/onboarding";
import { MapPin, Store, Globe, CalendarDays, XCircle } from "lucide-react";

const typeIcons: Record<string, React.ElementType> = {
  store: Store,
  webshop: Globe,
  event: CalendarDays,
  closed: XCircle,
};

const typeColors: Record<string, string> = {
  store: "default",
  webshop: "secondary",
  event: "outline",
  closed: "destructive",
};

interface EntityDiscoveryProps {
  installations: Installation[];
  onConfirm: (installations: Installation[]) => void;
  loading?: boolean;
}

export function EntityDiscovery({
  installations: initial,
  onConfirm,
  loading,
}: EntityDiscoveryProps) {
  const [items, setItems] = useState(initial);

  function toggleSelected(idx: number) {
    setItems((prev) =>
      prev.map((item, i) =>
        i === idx ? { ...item, selected: !item.selected } : item
      )
    );
  }

  function updateDisplayName(idx: number, name: string) {
    setItems((prev) =>
      prev.map((item, i) =>
        i === idx ? { ...item, display_name: name } : item
      )
    );
  }

  function updateType(idx: number, type: string) {
    setItems((prev) =>
      prev.map((item, i) =>
        i === idx ? { ...item, entity_type: type } : item
      )
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Review the discovered locations. Uncheck any that should be excluded.
        Edit display names and entity types as needed.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item, idx) => {
          const Icon = typeIcons[item.entity_type] || Store;
          return (
            <Card
              key={item.installation_id}
              className={!item.selected ? "opacity-50" : ""}
            >
              <CardContent className="flex items-start gap-3 pt-4">
                <Checkbox
                  checked={item.selected}
                  onCheckedChange={() => toggleSelected(idx)}
                />
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <Input
                      value={item.display_name}
                      onChange={(e) => updateDisplayName(idx, e.target.value)}
                      className="h-7 text-sm"
                    />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {item.installation_name}
                  </div>
                  <div className="flex items-center gap-2">
                    <Select
                      value={item.entity_type}
                      onValueChange={(v) => updateType(idx, v)}
                    >
                      <SelectTrigger className="h-7 w-32 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="store">Store</SelectItem>
                        <SelectItem value="webshop">Webshop</SelectItem>
                        <SelectItem value="event">Event</SelectItem>
                        <SelectItem value="closed">Closed</SelectItem>
                      </SelectContent>
                    </Select>
                    <Badge
                      variant={
                        (typeColors[item.entity_type] as "default" | "secondary" | "outline" | "destructive") ||
                        "default"
                      }
                      className="text-xs"
                    >
                      {item.entity_type}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      <div className="flex justify-end">
        <Button onClick={() => onConfirm(items)} disabled={loading}>
          {loading ? "Saving..." : "Confirm Entities"}
        </Button>
      </div>
    </div>
  );
}
