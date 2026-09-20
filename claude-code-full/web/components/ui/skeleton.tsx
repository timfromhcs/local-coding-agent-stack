import * as React from "react"
import { cn } from "@/lib/utils"

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted/20", className)}
      {...props}
    />
  )
}

export function ConversationLoadingSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <Skeleton className="h-10 w-3/4" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-12 w-1/2" />
    </div>
  )
}
