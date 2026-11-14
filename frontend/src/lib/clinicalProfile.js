/**
 * Pure presentation helpers for the medication clinical-knowledge views.
 *
 * Nothing in here contains medication content. Every clinical statement shown
 * in the UI comes from `GET /api/medications/<name>/clinical`; these helpers
 * only decide labels and ordering. An empty section is always presented as
 * "not assessed" — never as a zero-count "assessed" result.
 */

export const STATUS_META = Object.freeze({
  approved_findings: { label: 'Approved findings available', tone: 'safe' },
  awaiting_approval: { label: 'Awaiting clinical approval', tone: 'warning' },
  conflicting_evidence: { label: 'Conflicting evidence', tone: 'danger' },
  not_assessed: { label: 'Not assessed — no approved evidence', tone: 'neutral' },
});

export const ASSESSMENT_META = Object.freeze({
  not_assessed: 'Not yet assessed: no section has approved evidence.',
  partial: 'Partially assessed: some sections have approved evidence, others are missing.',
  approved_findings_in_every_section:
    'Every section has approved findings. This is still not a safety determination.',
});

const REVIEW_LABELS = {
  clinically_approved: 'Clinically approved',
  needs_clinical_review: 'Awaiting clinical review',
  rejected: 'Rejected by reviewer',
  withdrawn: 'Withdrawn',
  unverified_development_record: 'Unverified development record',
};

const CONFLICT_LABELS = {
  no_known_conflict: 'no known conflict',
  resolved: 'conflict resolved',
  conflicting_evidence: 'conflicting evidence',
  not_assessed: 'conflict not assessed',
};

const EXCLUSION_LABELS = {
  awaiting_clinical_approval: 'Not yet clinically approved',
  review_rejected: 'Rejected by a reviewer',
  review_withdrawn: 'Withdrawn',
  no_evidence_source: 'No evidence source recorded',
  conflict_assessment_missing: 'Conflict assessment missing',
  conflict_resolution_missing: 'Conflict marked resolved without a resolution',
  development_record_not_an_approval_authority: 'Development data cannot be an approval authority',
};

const STRENGTH_LABELS = { strong: 'Strong', moderate: 'Moderate', limited: 'Limited', unknown: 'Unknown' };

/** @returns {{label: string, tone: string}} */
export function statusMeta(status) {
  return STATUS_META[status] ?? { label: 'Not assessed — no approved evidence', tone: 'neutral' };
}

export function strengthLabel(strength) {
  return STRENGTH_LABELS[strength] ?? 'Unknown';
}

/** Domain sections in display order, with drug–drug interactions last. */
export function orderedSections(profile) {
  if (!profile || typeof profile !== 'object') return [];
  const domains = Object.values(profile.domains ?? {});
  return profile.drug_drug_interactions ? [...domains, profile.drug_drug_interactions] : domains;
}

/** Short, honest summary line for a collapsed section header. */
export function countSummary(section) {
  const counts = section?.counts ?? {};
  const approved = counts.approved ?? 0;
  const awaiting = counts.awaiting_approval ?? 0;
  const conflicting = counts.conflicting ?? 0;
  if (approved === 0 && awaiting === 0 && conflicting === 0) return 'Not assessed';
  const parts = [];
  if (approved > 0) parts.push(`${approved} approved`);
  if (awaiting > 0) parts.push(`${awaiting} awaiting approval`);
  if (conflicting > 0) parts.push(`${conflicting} conflicting`);
  return parts.join(' · ');
}

/** One-line, human-readable citation for a resolved evidence source. */
export function sourceCitation(source) {
  if (!source) return 'Unknown source';
  const bits = [source.publisher, source.document_title, source.document_version, source.publication_date]
    .filter((value) => typeof value === 'string' && value.trim());
  return bits.length > 0 ? bits.join(' — ') : source.source_id;
}

/** Only https URLs are ever turned into links. */
export function safeUrl(url) {
  return typeof url === 'string' && url.startsWith('https://') ? url : null;
}

export function assessmentSummary(profile) {
  return ASSESSMENT_META[profile?.assessment_state] ?? ASSESSMENT_META.not_assessed;
}

/** Unique, order-preserving medication names from plan entries. */
export function uniqueMedicationNames(entries) {
  const seen = new Set();
  const names = [];
  for (const entry of entries ?? []) {
    const name = typeof entry === 'string' ? entry : entry?.medication;
    const key = typeof name === 'string' ? name.trim().toLowerCase() : '';
    if (key && !seen.has(key)) {
      seen.add(key);
      names.push(name.trim());
    }
  }
  return names;
}

/** Review status as plain text; unknown values are never presented as approved. */
export function reviewStatusLabel(status) {
  return REVIEW_LABELS[status] ?? 'Not reviewed';
}

/** Conflict state as plain text; anything unrecognised reads as not assessed. */
export function conflictStatusLabel(status) {
  return CONFLICT_LABELS[status] ?? 'conflict not assessed';
}

/** Why a record is excluded from the approved findings (never its claim text). */
export function exclusionReasonLabel(reason) {
  return EXCLUSION_LABELS[reason] ?? 'Excluded: not eligible to be shown as a finding';
}

/** How many sections fall into each status bucket (for the card summary strip). */
export function statusTally(sections) {
  const tally = { approved_findings: 0, awaiting_approval: 0, conflicting_evidence: 0, not_assessed: 0 };
  for (const section of sections ?? []) {
    const key = section?.status in tally ? section.status : 'not_assessed';
    tally[key] += 1;
  }
  return tally;
}

/** True only when the backend says approved content comes from a verified active release. */
export function isAuthoritative(profile) {
  return profile?.knowledge?.approved_content_is_authoritative === true;
}
