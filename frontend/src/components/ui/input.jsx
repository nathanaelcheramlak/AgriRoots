import { cn } from "@/lib/utils";

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-[var(--radius)] border border-border bg-card px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted focus:border-primary",
        className
      )}
      {...props}
    />
  );
}
