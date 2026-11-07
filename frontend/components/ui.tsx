import type { ReactNode } from "react";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function Card({
  children,
  className,
  as: Tag = "div",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      className={cx(
        "rounded-2xl border border-sand/12 bg-forest-900/80 shadow-[0_1px_0_0_rgb(232_220_196/0.04)_inset,0_24px_48px_-24px_rgb(0_0_0/0.45)]",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function SectionTitle({ title, description, id }: { title: string; description?: ReactNode; id?: string }) {
  return (
    <div>
      <h3 id={id} className="text-base font-semibold tracking-tight">
        {title}
      </h3>
      {description ? <p className="mt-1 text-sm leading-relaxed text-sand/65">{description}</p> : null}
    </div>
  );
}

interface SegmentOption<T extends string | number> {
  value: T;
  label: string;
  title?: string;
}

/** Radio-group styled as a segmented control: native radios give arrow-key navigation for free. */
export function Segmented<T extends string | number>({
  name,
  legend,
  options,
  value,
  onChange,
  disabled,
  size = "md",
}: {
  name: string;
  legend: string;
  options: readonly SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  size?: "md" | "sm";
}) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="text-sm font-medium text-sand/90">{legend}</legend>
      <div
        className="mt-2 grid gap-1 rounded-xl border border-sand/12 bg-forest-950/60 p-1"
        style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
      >
        {options.map((o) => (
          <label key={String(o.value)} className="relative min-w-0" title={o.title}>
            <input
              type="radio"
              name={name}
              value={String(o.value)}
              checked={o.value === value}
              onChange={() => onChange(o.value)}
              className="peer sr-only"
            />
            <span
              className={cx(
                "block cursor-pointer truncate rounded-lg text-center font-medium text-sand/70 transition-colors",
                "hover:bg-sand/5 hover:text-sand",
                "peer-checked:bg-sand peer-checked:text-forest-950 peer-checked:shadow-sm",
                "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent-text",
                "peer-disabled:cursor-not-allowed peer-disabled:opacity-60",
                size === "md" ? "px-2 py-2.5 text-sm" : "px-1.5 py-2 text-[0.8125rem]",
              )}
            >
              {o.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("animate-shimmer rounded-lg bg-sand/8", className)} />;
}
