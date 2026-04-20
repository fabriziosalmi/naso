import React from 'react';
import { cn } from '@/lib/utils';
import { TableCell, TableRow } from '@/components/ui/table';

export function Skeleton({ className, ...props }) {
  return <div className={cn('skeleton', className)} aria-hidden="true" {...props} />;
}

export function SkeletonText({ width = 'w-32', className }) {
  return <Skeleton className={cn('h-3', width, className)} />;
}

export function SkeletonCircle({ size = 'h-8 w-8', className }) {
  return <Skeleton className={cn('rounded-full', size, className)} />;
}

export function SkeletonRow({ columns = 4, widths }) {
  const defaults = ['w-24', 'w-40', 'w-20', 'w-16'];
  return (
    <TableRow className="border-b border-white/[0.04]">
      {Array.from({ length: columns }).map((_, i) => (
        <TableCell key={i} className={i === columns - 1 ? 'text-right pr-5' : i === 0 ? 'pl-5' : ''}>
          <div className={i === columns - 1 ? 'flex justify-end' : 'flex items-center gap-3'}>
            {i === 0 && <SkeletonCircle size="h-7 w-7" />}
            <Skeleton className={cn('h-3', widths?.[i] ?? defaults[i] ?? 'w-24')} />
          </div>
        </TableCell>
      ))}
    </TableRow>
  );
}

export function SkeletonTable({ rows = 6, columns = 4, widths }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} columns={columns} widths={widths} />
      ))}
    </>
  );
}
