/**
 * @param {import('../api.js').ScheduleEntry[]} entries - already
 *   chronologically ordered by the backend (DailyPlan.entries).
 */
export default function ScheduleTimeline({ entries }) {
  if (entries.length === 0) {
    return (
      <p className="font-clarkson text-body-sm text-ash">
        No doses were scheduled for this plan.
      </p>
    );
  }

  return (
    <ol className="relative flex flex-col gap-32 border-l border-fog pl-32">
      {entries.map((entry, i) => (
        <li key={i} className="relative">
          <span
            className="absolute -left-[38px] top-[6px] h-12 w-12 rounded-full bg-obsidian"
            aria-hidden="true"
          />
          <time className="font-clarkson text-heading-sm font-light tracking-[-0.02em] text-obsidian">
            {entry.scheduled_time}
          </time>
          <p className="mt-4 font-clarkson text-subheading text-obsidian">{entry.medication}</p>
          <p className="mt-8 max-w-[60ch] font-clarkson text-body-sm leading-[1.5] text-ash">
            {entry.reasoning}
          </p>

          {entry.constraint_ids.length > 0 && (
            <ul className="mt-16 flex flex-wrap gap-8">
              {entry.constraint_ids.map((id) => (
                <li
                  key={id}
                  className="rounded-full border border-fog px-16 py-8 font-clarkson text-caption text-slate"
                >
                  {id}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  );
}