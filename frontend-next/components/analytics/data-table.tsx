"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface DataTableProps {
  columns: string[];
  data: (string | number | null)[][];
  maxRows?: number;
}

export function DataTable({ columns, data, maxRows = 100 }: DataTableProps) {
  const rows = data.slice(0, maxRows);

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead key={col} className="whitespace-nowrap">
                {col}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {row.map((cell, j) => (
                <TableCell key={j} className="whitespace-nowrap">
                  {cell ?? "—"}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data.length > maxRows && (
        <div className="p-2 text-center text-xs text-muted-foreground">
          Showing {maxRows} of {data.length} rows
        </div>
      )}
    </div>
  );
}
