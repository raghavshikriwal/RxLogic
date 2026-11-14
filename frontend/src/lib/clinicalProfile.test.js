import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  assessmentSummary, conflictStatusLabel, countSummary, exclusionReasonLabel, isAuthoritative, orderedSections,
  reviewStatusLabel, safeUrl, sourceCitation, statusMeta, statusTally, strengthLabel, uniqueMedicationNames,
} from './clinicalProfile.js';

test('an empty section is "not assessed", never a zero-count result', () => {
  const empty = { counts: { approved: 0, awaiting_approval: 0, conflicting: 0 } };
  assert.equal(countSummary(empty), 'Not assessed');
  assert.equal(countSummary(undefined), 'Not assessed');
  assert.ok(!/\b0\b/.test(countSummary(empty)));
});

test('count summary reports every non-zero bucket', () => {
  assert.equal(
    countSummary({ counts: { approved: 2, awaiting_approval: 1, conflicting: 1 } }),
    '2 approved · 1 awaiting approval · 1 conflicting',
  );
});

test('unknown statuses fall back to not assessed', () => {
  assert.equal(statusMeta('something_new').tone, 'neutral');
  assert.match(statusMeta('not_assessed').label, /Not assessed/);
  assert.equal(statusMeta('conflicting_evidence').tone, 'danger');
});

test('strength labels never upgrade unknown values', () => {
  assert.equal(strengthLabel('strong'), 'Strong');
  assert.equal(strengthLabel(undefined), 'Unknown');
  assert.equal(strengthLabel('definitive'), 'Unknown');
});

test('sections are ordered with drug–drug interactions last', () => {
  const profile = { domains: { a: { domain: 'a' }, b: { domain: 'b' } }, drug_drug_interactions: { domain: 'ddi' } };
  assert.deepEqual(orderedSections(profile).map((s) => s.domain), ['a', 'b', 'ddi']);
  assert.deepEqual(orderedSections(null), []);
});

test('citations are built only from recorded source metadata', () => {
  assert.equal(sourceCitation({ source_id: 'SRC-1', publisher: null, document_title: null }), 'SRC-1');
  assert.equal(
    sourceCitation({ source_id: 'SRC-1', publisher: 'Pub', document_title: 'Title', document_version: 'v2' }),
    'Pub — Title — v2',
  );
});

test('only https URLs become links', () => {
  assert.equal(safeUrl('https://dailymed.nlm.nih.gov/x'), 'https://dailymed.nlm.nih.gov/x');
  assert.equal(safeUrl('javascript:alert(1)'), null);
  assert.equal(safeUrl('http://example.com'), null);
  assert.equal(safeUrl(undefined), null);
});

test('assessment summary never claims safety', () => {
  assert.match(assessmentSummary({ assessment_state: 'approved_findings_in_every_section' }), /not a safety determination/);
  assert.match(assessmentSummary({}), /Not yet assessed/);
});

test('medication names are de-duplicated case-insensitively in order', () => {
  assert.deepEqual(
    uniqueMedicationNames([{ medication: 'Warfarin' }, { medication: 'warfarin' }, { medication: 'aspirin' }, {}]),
    ['Warfarin', 'aspirin'],
  );
});

test('unknown review states are never presented as approved', () => {
  assert.equal(reviewStatusLabel('clinically_approved'), 'Clinically approved');
  assert.equal(reviewStatusLabel('unverified_development_record'), 'Unverified development record');
  for (const unknown of [undefined, null, '', 'approved', 'reviewed', 'surprise']) {
    assert.ok(!/approved/i.test(reviewStatusLabel(unknown)), `${unknown} must not read as approved`);
  }
});

test('conflict labels distinguish "no known conflict" from "not assessed"', () => {
  assert.equal(conflictStatusLabel('no_known_conflict'), 'no known conflict');
  assert.equal(conflictStatusLabel('conflicting_evidence'), 'conflicting evidence');
  assert.equal(conflictStatusLabel(undefined), 'conflict not assessed');
  assert.equal(conflictStatusLabel('anything_else'), 'conflict not assessed');
});

test('exclusion reasons are explained and unknown reasons stay excluded', () => {
  assert.match(exclusionReasonLabel('conflict_assessment_missing'), /Conflict assessment missing/);
  assert.match(exclusionReasonLabel('no_evidence_source'), /No evidence source/);
  assert.match(exclusionReasonLabel('made_up'), /not eligible/);
});

test('status tally counts sections and treats unknown statuses as not assessed', () => {
  const tally = statusTally([
    { status: 'approved_findings' }, { status: 'awaiting_approval' }, { status: 'not_assessed' },
    { status: 'conflicting_evidence' }, { status: 'weird' }, undefined,
  ]);
  assert.deepEqual(tally, { approved_findings: 1, awaiting_approval: 1, conflicting_evidence: 1, not_assessed: 3 });
  assert.deepEqual(statusTally(undefined), { approved_findings: 0, awaiting_approval: 0, conflicting_evidence: 0, not_assessed: 0 });
});

test('only an explicit authoritative flag counts as authoritative', () => {
  assert.equal(isAuthoritative({ knowledge: { approved_content_is_authoritative: true } }), true);
  for (const value of [false, 'true', 1, undefined]) {
    assert.equal(isAuthoritative({ knowledge: { approved_content_is_authoritative: value } }), false);
  }
  assert.equal(isAuthoritative(undefined), false);
});
