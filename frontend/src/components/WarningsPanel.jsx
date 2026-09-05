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
              <span className="ml-auto font-clarkson text-caption text-slate">
                {Math.round(warning.confidence * 100)}% confidence
              </span>
            </div>

            <p className="mt-16 font-clarkson text-base leading-[1.5] text-paper">
              {warning.description}
            </p>

            <p className="mt-8 font-clarkson text-caption text-slate">
              Rule {warning.rule_id} · {warning.source}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}