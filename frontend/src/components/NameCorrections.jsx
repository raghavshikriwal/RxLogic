const MATCH_LABELS = {
  alias: 'brand name',
  fuzzy: 'spelling corrected',
};

/**
 * Shows every medication name the system changed before checking it
 * (brand -> generic, or a typo fix), so a correction is never applied
 * silently. Fuzzy matches are guesses, so they carry an explicit
 * prompt to confirm. Renders nothing when no name was changed.
 *
 * @param {{input_name: string, resolved_to: string, match: 'alias' | 'fuzzy'}[] | null | undefined} resolutions
 *   - plan.name_resolutions from the API; absent on plans that predate the field.
 */
export default function NameCorrections({ resolutions }) {
  if (!resolutions || resolutions.length === 0) return null;

  const hasFuzzy = resolutions.some((r) => r.match === 'fuzzy');

  return (
    <div className="rounded-lg border border-fog p-24">
      <p className="font-clarkson text-body-sm text-obsidian">Names we matched</p>
      <ul className="mt-8 flex flex-col gap-8">
        {resolutions.map((r) => (
          <li key={`${r.input_name}-${r.resolved_to}`} className="font-clarkson text-caption text-slate">
            <span className="text-obsidian">{r.input_name}</span> → {r.resolved_to}{' '}
            ({MATCH_LABELS[r.match] ?? r.match})
          </li>
        ))}
      </ul>
      {hasFuzzy && (
        <p className="mt-8 font-clarkson text-caption text-slate">
          Spelling corrections are best guesses. Check each one is the medication you meant.
        </p>
      )}
    </div>
  );
}
