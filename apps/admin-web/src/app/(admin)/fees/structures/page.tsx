/**
 * Fee Structures — list + create sheet with live-calculated line items.
 * UX: Serious, institutional. No flashy colors. Clean neutrals.
 * Permission: fees:read (list), fees:write (create)
 */

"use client";

import React, { useState, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import {
  Button, Badge, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { AcademicYear, FeeStructure } from "@eduzim/api-client";
import { school, fees } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Landmark, Plus, Trash2 } from "lucide-react";

interface LineItem {
  label: string;
  amount: string;
}

export default function FeeStructuresPage() {
  const t = useTranslations("fees");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selectedYearId, setSelectedYearId] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [yearId, setYearId] = useState("");
  const [items, setItems] = useState<LineItem[]>([{ label: "", amount: "" }]);

  const { data: years } = useApiQuery(() => school.listAcademicYears(), []);
  const { data: structures, isLoading, error, refetch } = useApiQuery(
    () => fees.listStructures(selectedYearId ? { year_id: selectedYearId } : undefined),
    [selectedYearId],
  );

  const yearMap = useMemo(() => {
    const m = new Map<string, AcademicYear>();
    years?.forEach((y: AcademicYear) => m.set(y.id, y));
    return m;
  }, [years]);

  const yearOptions = useMemo(() => {
    if (!years) return [];
    return [
      { value: "", label: t("allStatuses") },
      ...years.map((y: AcademicYear) => ({ value: y.id, label: y.name })),
    ];
  }, [years, t]);

  const formYearOptions = useMemo(() => {
    if (!years) return [];
    return years.map((y: AcademicYear) => ({ value: y.id, label: y.name }));
  }, [years]);

  const total = useMemo(
    () => items.reduce((sum, it) => sum + (parseFloat(it.amount) || 0), 0),
    [items],
  );

  const addItem = useCallback(() => {
    setItems((prev) => [...prev, { label: "", amount: "" }]);
  }, []);

  const removeItem = useCallback((idx: number) => {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const updateItem = useCallback((idx: number, field: keyof LineItem, value: string) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  }, []);

  const { mutate: create, isSubmitting } = useApiMutation(
    (data: Record<string, unknown>) => fees.createStructure(data),
    {
      onSuccess: () => {
        setSheetOpen(false);
        setName("");
        setYearId("");
        setItems([{ label: "", amount: "" }]);
        refetch();
      },
    },
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !yearId || items.length === 0) return;
    create({
      name,
      academic_year_id: yearId,
      items: items
        .filter((it) => it.label && it.amount)
        .map((it) => ({ label: it.label, amount: parseFloat(it.amount) })),
    });
  };

  const canSubmit = name && yearId && items.some((it) => it.label && parseFloat(it.amount) > 0);

  return (
    <RouteGuard permissions={["fees:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <PageHeader title={t("structures")} />
          <Button size="sm" onClick={() => setSheetOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            {t("createStructure")}
          </Button>
        </div>

        {/* Create structure sheet */}
        <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} width="max-w-lg">
          <SheetHeader>
            <SheetTitle>{t("createStructure")}</SheetTitle>
            <SheetDescription>{t("createStructureDescription")}</SheetDescription>
          </SheetHeader>
          <SheetBody>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("structureName")}</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder="e.g. Term 1 Fees 2026"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium">{t("academicYear")}</label>
                <Select
                  options={formYearOptions}
                  placeholder={t("selectYear")}
                  value={yearId}
                  onChange={(e) => setYearId(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">{t("lineItems")}</label>
                {items.map((item, idx) => (
                  <div key={idx} className="flex gap-2">
                    <input
                      type="text"
                      value={item.label}
                      onChange={(e) => updateItem(idx, "label", e.target.value)}
                      className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
                      placeholder={t("itemLabel")}
                    />
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={item.amount}
                      onChange={(e) => updateItem(idx, "amount", e.target.value)}
                      className="w-28 rounded-md border bg-background px-3 py-2 text-sm"
                      placeholder="0.00"
                    />
                    {items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeItem(idx)}
                        className="rounded-md p-2 text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={addItem}>
                  <Plus className="mr-1 h-3 w-3" /> {t("addItem")}
                </Button>
              </div>

              <div className="flex items-center justify-between rounded-md border bg-muted/30 px-4 py-3">
                <span className="text-sm font-medium">{t("totalAmount")}</span>
                <span className="text-lg font-bold">${total.toFixed(2)}</span>
              </div>

              <Button type="submit" className="w-full" disabled={!canSubmit || isSubmitting}>
                {isSubmitting ? t("creating") : t("createStructure")}
              </Button>
            </form>
          </SheetBody>
        </Sheet>

        {/* Year filter */}
        <div className="flex items-end gap-4">
          <div className="w-64 space-y-1">
            <label className="text-sm font-medium text-muted-foreground">{t("academicYear")}</label>
            <Select
              options={yearOptions}
              value={selectedYearId}
              onChange={(e) => setSelectedYearId(e.target.value)}
            />
          </div>
        </div>

        {error && <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}
          </div>
        ) : !structures || structures.length === 0 ? (
          <EmptyState icon={Landmark} title={t("noStructures")} description={t("noStructuresDescription")} />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("structureName")}</TableHead>
                  <TableHead>{t("totalAmount")}</TableHead>
                  <TableHead>{t("academicYear")}</TableHead>
                  <TableHead>{t("lineItems")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {structures.map((fs: FeeStructure) => (
                  <TableRow key={fs.id}>
                    <TableCell className="font-medium">{fs.name}</TableCell>
                    <TableCell className="font-mono">${fs.total.toFixed(2)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {yearMap.get(fs.academic_year_id)?.name ?? fs.academic_year_id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-sm">{fs.items.length} items</TableCell>
                    <TableCell>
                      <Badge variant={fs.is_active ? "default" : "secondary"}>
                        {fs.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
