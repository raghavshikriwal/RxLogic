import { useEffect, useState } from 'react';
import { getMedicationClinicalProfile } from '../api.js';
import MedicationProfileCard from './MedicationProfileCard.jsx';
import { uniqueMedicationNames } from '../lib/clinicalProfile.js';

/**
 * Loads each scheduled medication's clinical profile from the backend.
 * Nothing about a medication is hardcoded here; on failure the sections are
 * reported as unavailable, never silently shown as empty-but-assessed.
 */
export default function MedicationKnowledge({ medications }) {
  const names = uniqueMedicationNames(medications);
  const key = names.join('|').toLowerCase();
  const [state, setState] = useState({ status: 'loading', results: [] });

  useEffect(() => {
    if (names.length === 0) {
      setState({ status: 'ready', results: [] });
      return undefined;
    }
    const controller = new AbortController();
    setState({ status: 'loading', results: [] });
    Promise.all(
      names.map((name) =>
        getMedicationClinicalProfile(name, { signal: controller.signal })
          .then((profile) => ({ name, profile }))
          .catch((error) => ({ name, error: error?.message ?? 'Request failed.' })),
      ),
    ).then((results) => {
      if (!controller.signal.aborted) setState({ status: 'ready', results });
    });
    return () => controller.abort();
    // `key` captures the identity of the medication list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (names.length === 0) return null;
  return (
    <section aria-labelledby="medication-knowledge-heading" className="mt-16">
      <h3 id="medication-knowledge-heading" className="font-clarkson text-body-sm text-obsidian">Medication knowledge</h3>
      <p className="mt-4 font-clarkson text-caption text-slate">
        Expand a section to see approved findings, sources, evidence strength and what is still missing.
      </p>
      {state.status === 'loading' ? (
        <p className="mt-12 font-clarkson text-caption text-slate" role="status">Loading medication knowledge…</p>
      ) : (
        <div className="mt-12 flex flex-col gap-12">
          {state.results.map(({ name, profile, error }) =>
            profile ? (
              <MedicationProfileCard key={name} profile={profile} />
            ) : (
              <p key={name} className="rounded-lg border border-dashed border-slate p-12 font-clarkson text-caption text-obsidian" role="alert">
                Clinical knowledge for {name} is unavailable ({error}). Its sections are not assessed.
              </p>
            ),
          )}
        </div>
      )}
    </section>
  );
}
