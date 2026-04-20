import React from 'react';
import { Skeleton, SkeletonRow } from '@/components/ui/Skeleton';
import { Table, TableBody, TableHead, TableHeader, TableRow } from '@/components/ui/table';

/**
 * Placeholder shown while a lazy route chunk is loading. Approximates the
 * destination layout (header + grid + table) so the transition never shows
 * a blank shell.
 */
export default function RouteFallback() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading view">
      <div className="flex justify-between items-center">
        <div className="space-y-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-64" />
        </div>
        <Skeleton className="h-9 w-36 rounded-full" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[0, 1, 2].map(i => <Skeleton key={i} className="h-28 rounded-2xl" />)}
      </div>

      <div className="rounded-2xl border border-white/[0.06] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-white/[0.05] h-11">
              <TableHead className="pl-5"><Skeleton className="h-3 w-32" /></TableHead>
              <TableHead><Skeleton className="h-3 w-24" /></TableHead>
              <TableHead><Skeleton className="h-3 w-28" /></TableHead>
              <TableHead className="text-right pr-5"><Skeleton className="h-3 w-20 ml-auto" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} columns={4} />)}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
