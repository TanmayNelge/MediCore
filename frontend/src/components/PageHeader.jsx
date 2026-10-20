export default function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-7 flex-wrap animate-rise">
      <div className="flex items-stretch gap-3.5">
        <span className="w-1 rounded-full bg-gradient-to-b from-accent-bright to-accent-strong" />
        <div>
          <h1 className="text-[1.75rem] leading-tight font-display font-semibold m-0">{title}</h1>
          {subtitle && <p className="text-sm text-ink-muted mt-1 mb-0 max-w-2xl">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2.5 flex-wrap">{actions}</div>}
    </div>
  );
}
