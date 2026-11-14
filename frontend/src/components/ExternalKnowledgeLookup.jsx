import { useState } from 'react';
import { searchExternalMedicationSources } from '../api.js';

/** Explicit user-triggered retrieval. Results are evidence candidates, never approved findings. */
export default function ExternalKnowledgeLookup({ medicationName }) {
  const [state, setState] = useState({ status: 'idle', result: null, error: null });

  async function runLookup(refresh = false) {
    setState({ status: 'loading', result: null, error: null });
    try {
      const result = await searchExternalMedicationSources(medicationName, { refresh });
      setState({ status: 'ready', result, error: null });
    } catch (error) {
      setState({ status: 'error', result: null, error: error?.message ?? 'External lookup failed.' });
    }
  }

  return (
    <section className="mt-16 rounded-lg border border-fog p-12" aria-label={`External evidence lookup for ${medicationName}`}>
      <h4 className="font-clarkson text-body-sm text-obsidian">External medication sources</h4>
      <p className="mt-4 font-clarkson text-caption text-slate">
        Search official sources and stage source snapshots for human review. This does not approve or publish clinical findings.
      </p>
      <div className="mt-8 flex flex-wrap gap-8">
        <button type="button" disabled={state.status === 'loading'} onClick={() => runLookup(false)} className="rounded-lg border border-fog px-12 py-8 font-clarkson text-caption text-link-blue disabled:opacity-50">
          {state.status === 'loading' ? 'Searching sources…' : 'Search external sources'}
        </button>
        {state.result ? (
          <button type="button" disabled={state.status === 'loading'} onClick={() => runLookup(true)} className="rounded-lg border border-fog px-12 py-8 font-clarkson text-caption text-link-blue disabled:opacity-50">
            Refresh sources
          </button>
        ) : null}
      </div>
      {state.error ? <p className="mt-8 font-clarkson text-caption text-critical" role="alert">{state.error}</p> : null}
      {state.result ? (
        <div className="mt-12">
          <p className="font-clarkson text-caption font-semibold text-obsidian" role="status">Source lookup complete. Retrieved records remain unapproved and staged only.</p>
          <ul className="mt-8 flex flex-col gap-8">
            {state.result.results.map((item) => (
              <li key={item.source_id} className="rounded-lg bg-fog p-8">
                <div className="flex flex-wrap items-center justify-between gap-8">
                  <span className="font-clarkson text-caption font-semibold text-obsidian">{item.display_name}</span>
                  <span className="font-clarkson text-micro text-slate">{item.status}{item.cached ? ' · cached' : ''}</span>
                </div>
                {item.evidence_record_id ? <p className="mt-4 font-clarkson text-caption text-slate">Evidence {item.evidence_record_id} · {item.review_status} · {item.promotion_status}</p> : null}
                {item.result_count > 0 ? <p className="mt-4 font-clarkson text-caption text-slate">{item.result_count} source result(s)</p> : null}
                {item.source_url ? <a className="mt-4 inline-block break-all font-clarkson text-caption text-link-blue underline" href={item.source_url} target="_blank" rel="noreferrer">Open source query</a> : null}
                {item.message ? <p className="mt-4 font-clarkson text-caption text-slate">{item.message}</p> : null}
              </li>
            ))}
          </ul>
          <p className="mt-8 font-clarkson text-caption text-slate">Review staged evidence through the existing evidence-review workflow. Only separately curated, approved and released assertions can appear above as approved findings.</p>
        </div>
      ) : null}
    </section>
  );
}
