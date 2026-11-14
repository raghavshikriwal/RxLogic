import { useId, useState } from 'react';
import {
  conflictStatusLabel, countSummary, exclusionReasonLabel, reviewStatusLabel, safeUrl, sourceCitation, statusMeta,
  strengthLabel,
} from '../lib/clinicalProfile.js';

const TONE_CLASSES = {
  safe: 'bg-safe-wash text-safe',
  warning: 'bg-ember-wash text-ember',
  danger: 'bg-critical-wash text-critical',
  neutral: 'bg-canvas text-ash',
};

function SourceReference({ source }) {
  const url = safeUrl(source.canonical_url);
  return (
    <li className="font-clarkson text-caption text-slate">
      <span className="text-obsidian">{sourceCitation(source)}</span>
      {source.source_type ? ` · ${source.source_type.replaceAll('_', ' ')}` : ''}
      {source.jurisdiction ? ` · ${source.jurisdiction}` : ''}
      {source.retrieved_at ? ` · retrieved ${source.retrieved_at}` : ''}
      <span className="block">Source ID: {source.source_id}</span>
      {url ? (
        <a className="block break-all text-link-blue underline" href={url} target="_blank" rel="noopener noreferrer">{url}</a>
      ) : null}
    </li>
  );
}

function Finding({ finding }) {
  const dosage = finding.dosage_reference;
  return (
    <li className="rounded-lg bg-canvas p-12">
      {finding.subject ? <p className="font-clarkson text-caption text-slate">{finding.subject}</p> : null}
      <p className="font-clarkson text-body-sm text-obsidian">{finding.statement}</p>
      {dosage ? (
        <p className="mt-4 font-clarkson text-caption text-slate">
          Source-scoped reference — indication: {dosage.indication}; population: {dosage.population}; route: {dosage.route};
          frequency: {dosage.frequency}. Not a patient-specific dose.
        </p>
      ) : null}
      <dl className="mt-8 grid grid-cols-1 gap-4 font-clarkson text-caption text-slate sm:grid-cols-2">
        <div><dt className="inline">Evidence strength: </dt><dd className="inline text-obsidian">{strengthLabel(finding.evidence_strength)}</dd></div>
        <div><dt className="inline">Review status: </dt><dd className="inline text-obsidian">{reviewStatusLabel(finding.review_status)}</dd></div>
        <div>
          <dt className="inline">Conflict status: </dt>
          <dd className="inline text-obsidian">{conflictStatusLabel(finding.conflict_status)}</dd>
        </div>
        {finding.severity ? (
          <div><dt className="inline">Severity: </dt><dd className="inline text-obsidian">{finding.severity}</dd></div>
        ) : null}
        <div>
          <dt className="inline">Applicability: </dt>
          <dd className="inline text-obsidian">
            {finding.applicability?.jurisdiction ?? 'unspecified'}
            {finding.applicability?.notes ? ` — ${finding.applicability.notes}` : ''}
          </dd>
        </div>
      </dl>
      {finding.conflict_resolution ? (
        <p className="mt-4 font-clarkson text-caption text-slate">Conflict resolution: {finding.conflict_resolution}</p>
      ) : null}
      <p className="mt-8 font-clarkson text-caption text-slate">
        {finding.source_locator ? `Locator: ${finding.source_locator}` : 'Locator: not recorded for this finding'}
      </p>
      <p className="font-clarkson text-caption text-slate">Assertion {finding.assertion_id}</p>
      {finding.all_sources_resolved === false ? (
        <p className="mt-4 font-clarkson text-caption text-ember" role="note">
          Warning: one or more cited sources could not be resolved to a full citation record.
        </p>
      ) : null}
      <ul className="mt-4 flex flex-col gap-4">
        {(finding.sources ?? []).map((source) => (
          <SourceReference key={source.source_id} source={source} />
        ))}
      </ul>
    </li>
  );
}

/**
 * One expandable clinical domain. Collapsed, it shows only an honest status
 * and count summary; expanded, it shows approved findings with sources and
 * explicitly lists missing, pending and conflicting evidence.
 */
export default function KnowledgeSection({ section, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const panelId = useId();
  const meta = statusMeta(section.status);
  const findings = section.findings ?? [];
  const awaiting = section.awaiting_approval ?? [];
  const conflicts = section.conflicting_evidence ?? [];
  const missing = section.missing_evidence ?? [];

  return (
    <li className="rounded-lg border border-fog" data-domain={section.domain}>
      <h4>
        <button
          type="button"
          className="flex w-full flex-col items-start justify-between gap-8 p-16 text-left sm:flex-row sm:gap-12"
          aria-expanded={expanded}
          aria-controls={expanded ? panelId : undefined}
          onClick={() => setExpanded((value) => !value)}
        >
          <span>
            <span className="block font-clarkson text-body-sm text-obsidian">{section.label}</span>
            <span className="mt-4 block font-clarkson text-caption text-slate">{countSummary(section)}</span>
          </span>
          <span className="flex items-center gap-8">
            <span className={`rounded-lg px-8 py-4 font-clarkson text-micro ${TONE_CLASSES[meta.tone]}`}>{meta.label}</span>
            <span aria-hidden="true" className="font-clarkson text-caption text-slate">{expanded ? '−' : '+'}</span>
          </span>
        </button>
      </h4>
      {expanded ? (
        <div id={panelId} className="border-t border-fog p-16">
          {findings.length > 0 ? (
            <ul className="flex flex-col gap-12">
              {findings.map((finding) => <Finding key={finding.assertion_id} finding={finding} />)}
            </ul>
          ) : null}
          {missing.length > 0 ? (
            <div className="mt-12 rounded-lg border border-dashed border-slate p-12">
              <p className="font-clarkson text-caption text-obsidian">Missing evidence</p>
              <ul className="mt-4 list-disc pl-16 font-clarkson text-caption text-slate">
                {missing.map((message) => <li key={message}>{message}</li>)}
              </ul>
            </div>
          ) : null}
          {awaiting.length > 0 ? (
            <div className="mt-12 rounded-lg bg-ember-wash p-12">
              <p className="font-clarkson text-caption text-ember">
                {awaiting.length} record(s) await clinical approval and are not shown as findings
              </p>
              <ul className="mt-4 flex flex-col gap-4 font-clarkson text-caption text-obsidian">
                {awaiting.map((item) => (
                  <li key={item.assertion_id ?? item.rule_id}>
                    {item.assertion_id ?? item.rule_id}
                    {item.partner ? ` (with ${item.partner})` : ''}
                    {' · '}{reviewStatusLabel(item.review_status)}
                    {' · '}{conflictStatusLabel(item.conflict_status)}
                    {item.exclusion_reason ? ` · ${exclusionReasonLabel(item.exclusion_reason)}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {conflicts.length > 0 ? (
            <div className="mt-12 rounded-lg bg-critical-wash p-12" role="alert">
              <p className="font-clarkson text-caption text-critical">
                Conflicting evidence — excluded until a reviewer resolves it
              </p>
              <ul className="mt-4 font-clarkson text-caption text-obsidian">
                {conflicts.map((item) => (
                  <li key={item.assertion_id ?? item.rule_id}>
                    {item.assertion_id ?? item.rule_id}
                    {item.partner ? ` (with ${item.partner})` : ''}
                    {' · '}{reviewStatusLabel(item.review_status)}
                    {' · '}{(item.sources ?? []).map((s) => s.source_id).join(', ') || 'no source recorded'}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
