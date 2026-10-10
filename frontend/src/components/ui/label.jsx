import { cn } from "@/lib/utils";

export function Label({ className, ...props }) {
  return <label className={cn("mb-1 block text-sm font-medium text-foreground", className)} {...props} />;
}
