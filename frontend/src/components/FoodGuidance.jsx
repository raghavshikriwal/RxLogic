const REQUIREMENT_LABELS = {
  with_food: 'take with food',
  empty_stomach: 'take on an empty stomach',
  no_restriction: 'no meal timing needed',
};

const STATUS_LABELS = {
  applied: 'used in your schedule',
  matches_input: 'matches what you entered',
  informational: 'advice only',
};

/**
 * Shows each drug's meal guidance and how it was used, so a meal constraint
 * is never added (or ignored) silently. A conflict with what the user
 * entered is called out explicitly, because their choice is kept.
 * Renders nothing when no drug has a food rule.
 *
 * @param {{medication: string, requirement: string, status: string, note: string}[] | null | undefined} guidance
 *   - plan.food_guidance from the API; absent on plans that predate the field.
 */
export default function FoodGuidance({ guidance }) {
  if (!guidance || guidance.length === 0) return null;

  return (
    <div className="rounded-lg border border-fog p-24">
      <p className="font-clarkson text-body-sm text-obsidian">Food and timing</p>
      <ul className="mt-8 flex flex-col gap-8">
        {guidance.map((g) => (
          <li key={g.medication} className="font-clarkson text-caption text-slate">
            <span className="text-obsidian">{g.medication}</span>:{' '}
            {REQUIREMENT_LABELS[g.requirement] ?? g.requirement}
            {g.status === 'conflicts_with_input' ? (
              <span className="text-obsidian">
                {' '}
                (differs from your entry. We kept your choice, so check with your pharmacist.)
              </span>
            ) : (
              <> ({STATUS_LABELS[g.status] ?? g.status})</>
            )}
            {g.note && <span className="block">{g.note}</span>}
            <span className="block">{g.review_status === 'clinically_approved' ? 'Approved knowledge-release rule' : 'Unreviewed development rule — not clinical advice'}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
