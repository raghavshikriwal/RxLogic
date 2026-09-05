/**
 * @param {string[]} trace - plan.goal_trace, the order sub-goals were
 *   committed in. This is a real sequence, not decoration, so numbered
 *   markers are the right call here.
 */
export default function GoalTrace({ trace }) {
  if (trace.length === 0) return null;

  return (
    <details className="group rounded-lg border border-fog">
      <summary className="flex cursor-pointer list-none items-center justify-between px-24 py-16 font-clarkson text-body-sm text-obsidian">
        How this plan was reasoned through
        <span className="font-clarkson text-caption text-slate transition-transform duration-200 ease-editorial group-open:rotate-180">
          ▾
        </span>
      </summary>

      <ol className="flex flex-col gap-16 border-t border-fog px-24 py-24">
        {trace.map((step, i) => (
          <li key={i} className="flex gap-16">
            <span className="font-clarkson text-body-sm text-slate">{String(i + 1).padStart(2, '0')}</span>
            <span className="font-clarkson text-body-sm leading-[1.5] text-ash">{step}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}