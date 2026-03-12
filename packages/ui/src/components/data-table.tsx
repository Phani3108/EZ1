/**
 * DataTable — higher-level table wrapper built on the base Table primitives.
 * Handles column definitions, empty states, loading, and row click.
 *
 * Usage:
 *   <DataTable
 *     columns={[
 *       { key: "name", header: "Name", render: (row) => row.name },
 *       { key: "email", header: "Email" },
 *     ]}
 *     data={users}
 *     onRowClick={(row) => router.push(`/users/${row.id}`)}
 *     emptyMessage="No users found"
 *   />
 */

"use client";

import React from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "./table";
import { cn } from "../lib/utils";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  /** Custom render function. Falls back to row[key] */
  render?: (row: T, index: number) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  /** Unique key extractor. Defaults to (row as any).id ?? index */
  rowKey?: (row: T, index: number) => string | number;
  onRowClick?: (row: T) => void;
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  rowKey,
  onRowClick,
  loading = false,
  emptyMessage = "No data found",
  className,
}: DataTableProps<T>) {
  const getKey = rowKey ?? ((row: T, i: number) => (row as Record<string, unknown>).id as string ?? i);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead key={col.key} className={col.className}>
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="h-24 text-center text-muted-foreground"
              >
                {emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, i) => (
              <TableRow
                key={getKey(row, i)}
                className={cn(onRowClick && "cursor-pointer")}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <TableCell key={col.key} className={col.className}>
                    {col.render
                      ? col.render(row, i)
                      : (row[col.key] as React.ReactNode) ?? "—"}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
