import { BookOpen, ShieldCheck } from "lucide-react";

const SCHEMES = [
  "HDFC Mid Cap Fund Direct Growth",
  "HDFC Flexi Cap Direct Plan Growth",
  "HDFC Focused Fund Direct Growth",
  "HDFC ELSS Tax Saver Fund Direct Plan Growth",
  "HDFC Large Cap Fund Direct Growth",
];

export function InsightsPanel() {
  return (
    <aside className="hide-scrollbar hidden w-[320px] flex-col overflow-y-auto border-l border-surface-container-high bg-surface-container-low p-4 lg:flex">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold text-on-surface">
          Assistant scope
        </h2>
      </div>

      <div className="space-y-4">
        <div className="rounded-xl border border-surface-container-highest bg-surface-container p-4 shadow-card">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-secondary">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Compliance
          </div>
          <p className="text-sm leading-relaxed text-on-surface-variant">
            Answers use only the curated HDFC scheme corpus. No stock tips, no
            gold or commodity rates, and no other AMCs.
          </p>
        </div>

        <div className="rounded-xl border-l-4 border-l-primary border border-surface-container-highest bg-surface-container p-4 shadow-card">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-secondary">
            Supported schemes
          </div>
          <ul className="space-y-2 text-sm text-on-surface-variant">
            {SCHEMES.map((name) => (
              <li key={name} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span className="leading-snug">{name}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-surface-container-highest bg-surface-container p-4 shadow-card">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-secondary">
            <BookOpen className="h-4 w-4" />
            Topics
          </div>
          <p className="text-sm text-on-surface-variant">
            Expense ratio, exit load, minimum SIP, ELSS / 80C, benchmark,
            riskometer, NAV / AUM overview — grounded in retrieved passages.
          </p>
        </div>
      </div>
    </aside>
  );
}
