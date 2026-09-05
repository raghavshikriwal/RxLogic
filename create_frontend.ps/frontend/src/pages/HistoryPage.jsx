import { useEffect, useState } from 'react';
import { listPlans } from '../api.js';
import ErrorBanner from '../components/ErrorBanner.jsx';

const TIME_FORMAT = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

/** A minimal, dependency-free bar chart — one metric doesn't justify Chart.js. */
function WarningsTrend({ plans }) {
  const counts = plans.map((p) => p.warnings.length);
  const max = Math.max(1, ...counts);
  // Oldest first so the trend reads left-to-right chronologically.
  const chronological = [...plans].reverse();

  return (
    <div className="rounded-lg border border-fog p-32">
      <h3 className="font-clarkson text-body-sm text-ash">Warnings per plan, most recent {plans.length}</h3>
      <div className="mt-24 flex h-[120px] items-end gap-8">
        {chronological.map((p, i) => {
          const height = Math.max(4, (p.warnings.length / max) * 120);
          return (
            <div key={p.id ?? i} className="flex flex-1 flex-col items-center gap-8">
              <div
                className="w-full bg-obsidian transition-[height] duration-300 ease-editorial"
                style={{ height: `${height}px` }}
                title={`${p.warnings.length} warning${p.warnings.length === 1 ? '' : 's'}`}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PlanCard({ plan }) {
  return (
    <details className="group rounded-lg border border-fog">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-16 px-24 py-16">
        <div>
          <p className="font-clarkson text-body-sm text-obsidian">
            {plan.input_medications.map((m) => m.name).join(', ')}
          </p>
          <p className="mt-4 font-clarkson text-caption text-slate">
            {plan.created_at ? TIME_FORMAT.format(new Date(plan.created_at)) : 'Unknown time'} ·{' '}
            {plan.source === 'natural_language' ? 'Free text' : 'Structured'}
          </p>
        </div>
        <span
          className={[
            'rounded-full px-16 py-8 font-clarkson text-caption',
            plan.warnings.length > 0 ? 'bg-obsidian text-paper' : 'border border-fog text-ash',
          ].join(' ')}
        >
          {plan.warnings.length} warning{plan.warnings.length === 1 ? '' : 's'}
        </span>
      </summary>

      <div className="flex flex-col gap-16 border-t border-fog px-24 py-24">
        {plan.entries.map((entry, i) => (
          <div key={i} className="flex items-baseline gap-16">
            <span className="w-[56px] shrink-0 font-clarkson text-body-sm text-obsidian">
              {entry.scheduled_time}
            </span>
            <span className="font-clarkson text-body-sm text-ash">{entry.medication}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

export default function HistoryPage() {
  const [state, setState] = useState({ status: 'loading', plans: [], error: null });

  useEffect(() => {
    let cancelled = false;

    listPlans(20)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', plans: data.plans, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ status: 'error', plans: [], error: err });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="bg-paper py-80">
      <div className="mx-auto max-w-page px-24">
        <h1 className="font-clarkson text-heading text-obsidian">History</h1>
        <p className="mt-16 max-w-[60ch] font-clarkson text-body-sm text-ash">
          Every plan RxLogic has generated, kept for audit — nothing here is
          summarized away from what the reasoning core actually produced.
        </p>

        <div className="mt-56">
          {state.status === 'loading' && (
            <p className="font-clarkson text-body-sm text-ash">Loading plans…</p>
          )}

          {state.status === 'error' && <ErrorBanner error={state.error} />}

          {state.status === 'ready' && state.plans.length === 0 && (
            <p className="font-clarkson text-body-sm text-ash">
              No plans have been generated yet. Build one from the Plan tab.
            </p>
          )}

          {state.status === 'ready' && state.plans.length > 0 && (
            <div className="flex flex-col gap-40">
              <WarningsTrend plans={state.plans} />
              <div className="flex flex-col gap-16">
                {state.plans.map((plan, i) => (
                  <PlanCard key={plan.id ?? i} plan={plan} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}