import type { FriendlyError } from "@/lib/errors";
import { AlertIcon, PathsIcon } from "./icons";
import { Card, Skeleton } from "./ui";

export function EmptyState() {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center sm:py-20">
      <span className="flex size-14 items-center justify-center rounded-2xl border border-sand/15 bg-forest-950/60">
        <PathsIcon className="size-7 text-sand/80" />
      </span>
      <h2 className="mt-5 text-lg font-semibold tracking-tight">Pick a stock to begin</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-sand/65">
        Type a ticker or tap an example above, choose how far ahead to look, then run the simulation.
        Results show up here.
      </p>
    </Card>
  );
}

export function ErrorAlert({ error, onRetry }: { error: FriendlyError; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-4 rounded-2xl border border-sand/35 bg-sand/[0.07] p-5 sm:flex-row sm:items-start sm:p-6"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-sand/12">
        <AlertIcon className="size-5 text-sand" />
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="font-semibold tracking-tight">{error.title}</h2>
        <p className="mt-1 text-sm leading-relaxed text-sand/75">{error.message}</p>
      </div>
      {onRetry && error.code !== "invalid_input" ? (
        <button
          type="button"
          onClick={onRetry}
          className="self-start rounded-lg border border-sand/30 px-3.5 py-2 text-sm font-medium transition-colors hover:bg-sand/10"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

const SKELETON_BARS = [8, 14, 24, 38, 56, 72, 84, 90, 80, 66, 50, 38, 28, 20, 14, 10, 7, 5, 4, 3];

export function ResultsSkeleton() {
  return (
    <div className="grid gap-5 sm:gap-6" aria-hidden>
      <Card className="p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-8 w-56" />
            <Skeleton className="h-4 w-72 max-w-full" />
          </div>
          <div className="space-y-3 sm:flex sm:flex-col sm:items-end">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-9 w-36" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Card key={i} className="space-y-4 p-5">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-3 w-full" />
          </Card>
        ))}
      </div>
      <Card className="p-5 sm:p-7">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="mt-2 h-4 w-80 max-w-full" />
        <div className="relative mt-6 h-[300px] overflow-hidden rounded-xl sm:h-[400px]">
          <Skeleton className="absolute inset-0 rounded-xl" />
          <svg viewBox="0 0 400 200" preserveAspectRatio="none" className="absolute inset-0 size-full opacity-40">
            <path d="M0 110 C 80 108, 160 80, 400 40 L 400 180 C 160 140, 80 115, 0 110 Z" fill="rgb(139 92 246 / 0.25)" />
          </svg>
        </div>
      </Card>
      <div className="grid gap-5 sm:gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card className="p-5 sm:p-7">
          <Skeleton className="h-5 w-52" />
          <div className="mt-6 flex h-[220px] items-end gap-1">
            {SKELETON_BARS.map((h, i) => (
              <div key={i} className="animate-shimmer flex-1 rounded-t-sm bg-sand/8" style={{ height: `${h}%` }} />
            ))}
          </div>
        </Card>
        <Card className="space-y-4 p-5 sm:p-7">
          <Skeleton className="h-5 w-44" />
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </Card>
      </div>
    </div>
  );
}
