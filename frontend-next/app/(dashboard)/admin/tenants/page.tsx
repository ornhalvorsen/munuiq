"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  listTenants,
  createTenant,
  deleteTenant,
  Tenant,
  listUsers,
  User,
} from "@/lib/api/admin";
import { assignTenant } from "@/lib/api/admin";
import { Plus, Trash2, Users, UserPlus } from "lucide-react";

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(
    null
  );
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [form, setForm] = useState({ name: "", customer_ids: "" });

  async function loadData() {
    try {
      const [t, u] = await Promise.all([listTenants(), listUsers()]);
      setTenants(t);
      setAllUsers(u);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleCreate() {
    const ids = form.customer_ids
      .split(",")
      .map((s) => parseInt(s.trim()))
      .filter((n) => !isNaN(n));
    if (!form.name || ids.length === 0) return;
    await createTenant({ name: form.name, customer_ids: ids });
    setDialogOpen(false);
    setForm({ name: "", customer_ids: "" });
    loadData();
  }

  async function handleDelete(tenantId: number) {
    if (!confirm("Delete this tenant?")) return;
    await deleteTenant(tenantId);
    loadData();
  }

  async function handleAssign() {
    if (!selectedTenantId || !selectedUserId) return;
    await assignTenant(Number(selectedUserId), selectedTenantId);
    setAssignDialogOpen(false);
    setSelectedUserId("");
    loadData();
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tenants</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-1 h-4 w-4" />
              Add tenant
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create tenant</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, name: e.target.value }))
                  }
                  placeholder="Restaurant Chain A"
                />
              </div>
              <div>
                <Label>Customer IDs (comma-separated)</Label>
                <Input
                  value={form.customer_ids}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      customer_ids: e.target.value,
                    }))
                  }
                  placeholder="761, 10352"
                />
              </div>
              <Button onClick={handleCreate} className="w-full">
                Create
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {tenants.map((t) => (
          <Card key={t.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                {t.name}
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => {
                      setSelectedTenantId(t.id);
                      setAssignDialogOpen(true);
                    }}
                  >
                    <UserPlus className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive"
                    onClick={() => handleDelete(t.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground">Customer IDs</p>
                <div className="flex flex-wrap gap-1">
                  {t.customer_ids.map((id) => (
                    <Badge key={id} variant="secondary" className="text-xs">
                      {id}
                    </Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  <Users className="mr-1 inline-block h-3 w-3" />
                  Users ({t.users.length})
                </p>
                {t.users.length > 0 ? (
                  <div className="mt-1 space-y-1">
                    {t.users.map((u) => (
                      <div
                        key={u.id}
                        className="flex items-center gap-2 text-sm"
                      >
                        <span>{u.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {u.role}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-muted-foreground">
                    No users assigned
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Assign user dialog */}
      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign user to tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>User</Label>
              <Select
                value={selectedUserId}
                onValueChange={setSelectedUserId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select user" />
                </SelectTrigger>
                <SelectContent>
                  {allUsers.map((u) => (
                    <SelectItem key={u.id} value={u.id.toString()}>
                      {u.name} ({u.email})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handleAssign} className="w-full">
              Assign
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
