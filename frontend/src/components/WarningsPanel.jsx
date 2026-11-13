/**
 * Severity is communicated through fill weight and border treatment,
 * not color — the palette is strictly monochrome, so "severe" reads
 * as a solid obsidian badge, "mild" as a quiet outline. This keeps the
 * hierarchy legible without breaking the design system's one rule.
 */
const SEVERITY_STYLE = {
  severe: 'bg-obsidian text-paper border border-obsidian',
  moderate: 'bg-charcoal text-paper border border-charcoal',
  mild: 'bg-transparent text-obsidian border border-obsidian',
  unknown: 'bg-transparent text-slate border border-dashed border-slate',
};

const SEVERITY_LABEL = {
  severe: 'Severe',
  moderate: 'Moderate',
  mild: 'Mild',
  unknown: 'Unknown risk',
};

const EVIDENCE_LABEL = {
  strong: 'Strong evidence',
  moderate: 'Moderate evidence',
  limited: 'Limited evidence',
  unknown: 'Evidence not rated',
};

/**
 * Formats a gap in minutes for people: 480 -> "8 h", 90 -> "1 h 30 min", 45 -> "45 min".
 * @param {number} minutes
 */
function formatGap(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} min`;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

/**
 * One sentence of spacing advice for a warning, or null when its rule records none.
 * An order-aware rule describes the window around the anchor drug's dose.
 */
function spacingAdvice(warning) {
  const { ordering, separation_minutes: separation } = warning;
  if (ordering) {
    const other =
      warning.medication_a === ordering.anchor ? warning.medication_b : warning.medication_a;
    return `Take ${other} at least ${formatGap(ordering.after_minutes)} after ${ordering.anchor}, or at least ${formatGap(ordering.before_minutes)} before it.`;
  }
  if (separation != null) {
    return `Keep doses at least ${formatGap(separation)} apart.`;
  }
  return null;
}

/**
 * @param {import('../api.js').Interaction[]} warnings
 */
export default function WarningsPanel({ warnings }) {
  if (warnings.length === 0) {
    return (
      <div className="rounded-lg border border-fog bg-paper p-32">
        <p className="font-clarkson text-body-sm text-ash">
          No interactions were flagged for this combination.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-obsidian p-32 text-paper">
      <h3 className="font-clarkson text-subheading">
        {warnings.length} interaction{warnings.length === 1 ? '' : 's'} to review
      </h3>

      <ul className="mt-24 flex flex-col gap-24">
        {warnings.map((warning, i) => (
          <li key={i} className="border-t border-charcoal pt-24 first:border-t-0 first:pt-0">
            <div className="flex flex-wrap items-center gap-16">
              <span
                className={`rounded-full px-16 py-8 font-clarkson text-caption uppercase tracking-[0.04em] ${SEVERITY_STYLE[warning.severity] ?? SEVERITY_STYLE.unknown}`}
              >
                {SEVERITY_LABEL[warning.severity] ?? SEVERITY_LABEL.unknown}
              </span>
              <span className="font-clarkson text-body-sm text-ash">
                {warning.medication_a} + {warning.medication_b}
              </span>
              <span className="font-clarkson text-caption text-slate">
                {EVIDENCE_LABEL[warning.evidence] ?? EVIDENCE_LABEL.unknown}
              </span>
              <span className="ml-auto font-clarkson text-caption text-slate">
                {Math.round(warning.confidence * 100)}% rule-match confidence
              </span>
            </div>

            <p className="mt-16 font-clarkson text-base leading-[1.5] text-paper">
              {warning.description}
            </p>

            {spacingAdvice(warning) && (
              <p className="mt-8 font-clarkson text-body-sm text-ash">{spacingAdvice(warning)}</p>
            )}

            <p className="mt-8 font-clarkson text-caption text-slate">
              Rule {warning.rule_id} · {warning.source}
            </p>
            <p className="mt-4 font-clarkson text-caption text-slate">
              {warning.review_status === 'clinically_approved'
                ? 'Approved knowledge-release rule'
                : 'Unreviewed development rule — not a clinically approved finding'}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}