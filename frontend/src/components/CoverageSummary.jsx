/**
 * Tells the reader how much of their medication list was actually
 * checked. "No interactions flagged" is only reassuring when every
 * drug was covered, so this sits directly above the interaction
 * results. Incomplete coverage gets a dashed border, matching the
 * "unknown risk" treatment in WarningsPanel (monochrome palette).
 *
 * @param {{summary: string, is_complete: boolean, unchecked: string[]} | null | undefined} coverage
 *   - plan.coverage from the API; absent on plans that predate the field.
 */
export default function CoverageSummary({ coverage }) {
  if (!coverage) return null;

  const { summary, is_complete: isComplete, unchecked } = coverage;

  return (
    <div className={`rounded-lg border p-24 ${isComplete ? 'border-fog' : 'border-dashed border-slate'}`}>
      <p className="font-clarkson text-body-sm text-obsidian">{summary}</p>
      {!isComplete && (
        <p className="mt-8 font-clarkson text-caption text-slate">
          Not covered by the knowledge base: {unchecked.join(', ')}. Treat this check as incomplete.
        </p>
      )}
    </div>
  );
}
