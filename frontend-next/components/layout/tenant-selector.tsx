"use client";

import { useTenant } from "@/providers/tenant-provider";
import { useAuth } from "@/providers/auth-provider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function TenantSelector() {
  const { user } = useAuth();
  const { selectedCustomerId, customerList, selectCustomer } = useTenant();

  // Superadmins don't have customer_ids filter
  if (!user || user.role === "superadmin") {
    return (
      <div className="text-sm text-muted-foreground">
        {user?.tenant_name || "All customers"}
      </div>
    );
  }

  if (customerList.length <= 1) {
    return (
      <div className="text-sm text-muted-foreground">
        Customer {selectedCustomerId || "—"}
      </div>
    );
  }

  return (
    <Select
      value={selectedCustomerId?.toString() || ""}
      onValueChange={(v) => selectCustomer(Number(v))}
    >
      <SelectTrigger className="w-48">
        <SelectValue placeholder="Select customer" />
      </SelectTrigger>
      <SelectContent>
        {customerList.map((id) => (
          <SelectItem key={id} value={id.toString()}>
            Customer {id}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
