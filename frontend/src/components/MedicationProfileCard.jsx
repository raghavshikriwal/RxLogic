import { useState } from 'react';
import KnowledgeSection from './KnowledgeSection.jsx';
import { assessmentSummary, isAuthoritative, orderedSections, statusTally } from '../lib/clinicalProfile.js';

const TALLY_ITEMS = [
  ['approved_findings', 'with approved findings', 'bg-safe-wash text-safe'],
  ['awaiting_approval', 'awaiting approval', 'bg-ember-wash text-ember'],
  ['conflicting_evidence', 'with conflicting evidence', 'bg-critical-wash text-critical'],
  ['not_assessed', 'not assessed', 'bg-canvas text-ash'],
];

/**
 * Presentational card for one medication's clinical knowledge profile.
 * `profile` is the unmodified response of GET /api/medications/<name>/clinical.
 * Every count shown here is derived from that response; nothing is filled in.
 */
export default function MedicationProfileCard({ profile, defaultExpanded = false }) {
  const medication = profile.medication;
  const sections = orderedSections(profile);
  const tally = statusTally(sections);
  const [openAll, setOpenAll] = useState(defaultExpanded);
  const [epoch, setEpoch] = useState(0);
  const toggleAll = () => {
    setOpenAll((value) => !value);
    setEpoch((value) => value + 1); // remount sections so each adopts the new default
  };

  return (
    <article className="rounded-lg border border-fog p-16 sm:p-24" aria-label={`Clinical knowledge for ${medication.canonical_name}`}>
      <header>
        <h3 className="font-clarkson text-body-sm text-obsidian">{medication.canonical_name}</h3>
        <p className="mt-4 break-words font-clarkson text-caption text-slate">
          RxCUI {medication.rxcui}
          {medication.aliases?.length ? ` · also known as ${medication.aliases.join(', ')}` : ''}
        </p>
        <p className="mt-8 font-clarkson text-caption text-obsidian">{assessmentSummary(profile)}</p>
        <p className="mt-4 font-clarkson text-caption text-slate">
          {profile.sections_with_approved_findings} of {profile.section_count} sections have approved findings
          · release {profile.knowledge?.release}
        </p>
        {!isAuthoritative(profile) ? (
          <p className="mt-8 rounded-lg border border-dashed border-slate p-12 font-clarkson text-caption text-obsidian" role="note">
            Development knowledge mode: records in the development files are never shown as approved findings.
            Approved content appears only when the app runs against a promoted knowledge release.
          </p>
        ) : null}
        <ul className="mt-12 flex flex-wrap gap-8" aria-label="Section status summary">
          {TALLY_ITEMS.map(([key, label, tone]) => (
            <li key={key} className={`rounded-lg px-8 py-4 font-clarkson text-micro ${tone}`}>
              {tally[key]} {label}
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-12 rounded-lg border border-fog px-12 py-8 font-clarkson text-caption text-link-blue"
          onClick={toggleAll}
        >
          {openAll ? 'Collapse all sections' : 'Expand all sections'}
        </button>
      </header>
      <ul className="mt-16 flex flex-col gap-8">
        {sections.map((section) => (
          <KnowledgeSection key={`${section.domain}-${epoch}`} section={section} defaultExpanded={openAll} />
        ))}
      </ul>
      <p className="mt-16 font-clarkson text-caption text-slate">{profile.interpretation}</p>
      <p className="mt-8 font-clarkson text-caption font-semibold text-obsidian">{profile.disclaimer}</p>
    </article>
  );
}
