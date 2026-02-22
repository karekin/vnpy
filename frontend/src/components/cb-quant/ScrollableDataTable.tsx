import { Table, TableBody, TableCell, TableHeader, TableRow } from "@/components/ui/table";
import React from "react";

type ScrollableDataTableProps = {
  headers: React.ReactNode[];
  minTableWidthClass: string;
  colSpan: number;
  isEmpty: boolean;
  emptyText?: string;
  children: React.ReactNode;
};

export default function ScrollableDataTable({
  headers,
  minTableWidthClass,
  colSpan,
  isEmpty,
  emptyText = "暂无符合筛选条件的数据",
  children,
}: ScrollableDataTableProps) {
  return (
    <div className="max-h-[560px] overflow-x-auto overflow-y-auto rounded-xl border border-gray-200 dark:border-gray-800 [&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 dark:[&::-webkit-scrollbar-thumb]:bg-gray-600 [scrollbar-gutter:stable_both-edges]">
      <div className={`inline-block ${minTableWidthClass} align-top`}>
        <Table className="w-full">
          <TableHeader>
            <TableRow className="border-b border-gray-200 dark:border-gray-800">
              {headers.map((header, index) => (
                <TableCell
                  key={`header-${index}`}
                  isHeader
                  className="sticky top-0 z-10 bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 whitespace-nowrap dark:bg-gray-900"
                >
                  {header}
                </TableCell>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {children}
            {isEmpty && (
              <TableRow>
                <td colSpan={colSpan} className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                  {emptyText}
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
