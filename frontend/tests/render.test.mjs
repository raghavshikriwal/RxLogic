/**
 * Server-side render tests for the clinical knowledge components.
 *
 * Uses only tooling already installed with the frontend (esbuild ships with
 * Vite; react-dom/server ships with react-dom). Fixtures are SYNTHETIC test
 * data shaped like GET /api/medications/<name>/clinical; they are never
 * shipped to the application.
 */
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, '../src/components');
let workdir;
const loaded = {};

async function load(name) {
  const result = await build({
    entryPoints: [path.join(src, `${name}.jsx`)],
    bundle: true, write: false, format: 'esm', platform: 'node', jsx: 'automatic',
    external: ['react', 'react-dom', 'react/jsx-runtime'],
    loader: { '.js': 'jsx' }, define: { 'import.meta.env': '{}' }, logLevel: 'silent',
  });
  const file = path.join(workdir, `${name}.mjs`);
  await writeFile(file, result.outputFiles[0].text);
  return (await import(pathToFileURL(file).href)).default;
}

before(async () => {
  workdir = await mkdtemp(path.join(here, '.render-'));
  for (const name of ['MedicationProfileCard', 'KnowledgeSection', 'ClinicalAssessment']) {
    loaded[name] = await load(name);
  }
});
after(async () => { await rm(workdir, { recursive: true, force: true }); });

const emptySection = (domain, label) => ({
  domain, label, status: 'not_assessed',
  counts: { approved: 0, awaiting_approval: 0, conflicting: 0 },
  findings: [], awaiting_approval: [], conflicting_evidence: [],
  missing_evidence: ['No clinically approved assertion is available for this domain.'],
});

const source = {
  source_id: 'SRC-TEST-1', publisher: 'Synthetic Publisher', source_type: 'fda_label',
  document_title: 'Synthetic label', document_version: 'v9', publication_date: '2026-01-01',
  retrieved_at: '2026-02-02', jurisdiction: 'US', canonical_url: 'https://example.gov/label', resolved: true,
};

function profile(overrides = {}) {
  return {
    schema_version: '1.0.0',
    medication: { canonical_name: 'testmed', rxcui: '1', aliases: ['tm'] },
    knowledge: { mode: 'active_release', release: 'RXK-TEST', approved_content_is_authoritative: true, clinical_use_permitted: false },
    assessment_state: 'not_assessed', sections_with_approved_findings: 0, section_count: 2,
    domains: { contraindications: emptySection('contraindications', 'Contraindications') },
    drug_drug_interactions: emptySection('drug_drug_interactions', 'Drug–drug interactions'),
    interpretation: 'Empty or missing sections mean not assessed, never absence of risk.',
    disclaimer: 'Educational demonstrator only. Clinical use is not permitted.',
    ...overrides,
  };
}

const render = (name, props) => renderToStaticMarkup(createElement(loaded[name], props));

test('unassessed medication shows "Not assessed", never zero counts', () => {
  const html = render('MedicationProfileCard', { profile: profile() });
  assert.match(html, /Not assessed/);
  assert.doesNotMatch(html, /\b0 approved\b/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /Educational demonstrator only/);
});

test('expanding an unassessed section lists the missing evidence', () => {
  const html = render('MedicationProfileCard', { profile: profile(), defaultExpanded: true });
  assert.match(html, /Missing evidence/);
  assert.match(html, /No clinically approved assertion/);
});

test('approved finding shows statement, source, locator, strength and review status', () => {
  const section = {
    ...emptySection('contraindications', 'Contraindications'), status: 'approved_findings',
    counts: { approved: 1, awaiting_approval: 0, conflicting: 0 }, missing_evidence: [],
    findings: [{
      assertion_id: 'CONTRAINDICATION-KNC-1', medication: 'testmed', domain: 'contraindications',
      subject: 'synthetic condition', statement: 'Synthetic statement for rendering only.',
      evidence_source_ids: ['SRC-TEST-1'], sources: [source], source: 'Synthetic', source_locator: 'Section 4; set_id=abc',
      evidence_strength: 'strong', review_status: 'clinically_approved', conflict_status: 'no_known_conflict',
      conflict_resolution: '', applicability: { jurisdiction: 'US', notes: 'adults only' },
    }],
  };
  const html = render('KnowledgeSection', { section, defaultExpanded: true });
  for (const expected of [
    'Synthetic statement for rendering only.', 'Synthetic Publisher', 'Locator: Section 4; set_id=abc',
    'SRC-TEST-1', 'Strong', 'Clinically approved', 'no known conflict', 'adults only', 'rel="noopener noreferrer"',
  ]) assert.ok(html.includes(expected), `missing ${expected}`);
  assert.match(html, /1 approved/);
});

test('non-https source URLs are never rendered as links', () => {
  const bad = { ...source, canonical_url: 'javascript:alert(1)' };
  const section = {
    ...emptySection('contraindications', 'Contraindications'), status: 'approved_findings',
    counts: { approved: 1, awaiting_approval: 0, conflicting: 0 },
    findings: [{ assertion_id: 'A1', statement: 'x', sources: [bad], evidence_strength: 'unknown', applicability: {} }],
  };
  assert.doesNotMatch(render('KnowledgeSection', { section, defaultExpanded: true }), /javascript:/);
});

test('conflicting evidence is announced and awaiting records show IDs only', () => {
  const section = {
    ...emptySection('precautions', 'Precautions'), status: 'conflicting_evidence',
    counts: { approved: 0, awaiting_approval: 1, conflicting: 1 },
    awaiting_approval: [{ assertion_id: 'PEND-1', review_status: 'needs_clinical_review' }],
    conflicting_evidence: [{ assertion_id: 'CONF-1', sources: [source] }],
  };
  const html = render('KnowledgeSection', { section, defaultExpanded: true });
  assert.match(html, /role="alert"/);
  assert.match(html, /CONF-1/);
  assert.match(html, /PEND-1/);
  assert.match(html, /await clinical approval/);
});

test('clinical assessment does not show zero-count domains as assessed', () => {
  const assessment = {
    findings: [], unresolved_conflicts: [], interpretation: 'No approved finding was produced.',
    dosage_safety: { message: 'RxLogic does not calculate a dose.' },
    domains: {
      contraindications: { status: 'no_approved_assertions', approved_assertions_available: 0, excluded_unapproved_or_conflicted: 0 },
    },
  };
  const html = render('ClinicalAssessment', { assessment, medications: [] });
  assert.match(html, /Not assessed — no approved evidence available/);
  assert.doesNotMatch(html, /0 approved/);
  assert.match(html, /Clinical use is not permitted/);
});

test('development knowledge mode is announced and never looks like an approved release', () => {
  const dev = profile({ knowledge: { mode: 'legacy_development', release: 'dev', approved_content_is_authoritative: false, clinical_use_permitted: false } });
  assert.match(render('MedicationProfileCard', { profile: dev }), /Development knowledge mode/);
  assert.doesNotMatch(render('MedicationProfileCard', { profile: profile() }), /Development knowledge mode/);
});

test('summary strip reports section counts taken from the profile', () => {
  const html = render('MedicationProfileCard', { profile: profile() });
  assert.match(html, /2 not assessed/);
  assert.match(html, /0 with approved findings/); // a tally of sections, labelled as such
  assert.match(html, /Expand all sections/);
});

test('awaiting records show review state, conflict state and reason but never claim text', () => {
  const section = {
    ...emptySection('precautions', 'Precautions'), status: 'awaiting_approval',
    counts: { approved: 0, awaiting_approval: 2, conflicting: 0 },
    awaiting_approval: [
      { assertion_id: 'PEND-1', review_status: 'needs_clinical_review', conflict_status: 'not_assessed', exclusion_reason: 'awaiting_clinical_approval' },
      { assertion_id: 'DEV-1', review_status: 'unverified_development_record', recorded_review_status: 'clinically_approved',
        conflict_status: 'no_known_conflict', exclusion_reason: 'development_record_not_an_approval_authority' },
    ],
  };
  const html = render('KnowledgeSection', { section, defaultExpanded: true });
  for (const expected of ['Awaiting clinical review', 'conflict not assessed', 'Not yet clinically approved',
    'Unverified development record', 'Development data cannot be an approval authority']) {
    assert.ok(html.includes(expected), `missing ${expected}`);
  }
  assert.doesNotMatch(html, /Clinically approved/); // nothing here may read as approved
});

test('a finding without a locator or with unresolved sources says so instead of hiding it', () => {
  const section = {
    ...emptySection('precautions', 'Precautions'), status: 'approved_findings',
    counts: { approved: 1, awaiting_approval: 0, conflicting: 0 }, missing_evidence: [],
    findings: [{ assertion_id: 'A9', statement: 'Synthetic.', sources: [{ source_id: 'SRC-X', resolved: false }],
      all_sources_resolved: false, evidence_strength: 'limited', review_status: 'clinically_approved',
      conflict_status: 'resolved', conflict_resolution: 'Synthetic resolution.', applicability: {} }],
  };
  const html = render('KnowledgeSection', { section, defaultExpanded: true });
  assert.match(html, /Locator: not recorded/);
  assert.match(html, /could not be resolved/);
  assert.match(html, /conflict resolved/);
  assert.match(html, /Synthetic resolution\./);
});

test('missing evidence is stated separately from approved findings in the same section', () => {
  const section = { ...emptySection('contraindications', 'Contraindications'), status: 'approved_findings',
    counts: { approved: 1, awaiting_approval: 0, conflicting: 0 },
    findings: [{ assertion_id: 'D1', statement: 'Synthetic dosage note.', sources: [source], evidence_strength: 'unknown', applicability: {} }],
    missing_evidence: ['Dosage entries are source-scoped references, not patient-specific doses.'] };
  const html = render('KnowledgeSection', { section, defaultExpanded: true });
  assert.match(html, /Missing evidence/);
  assert.match(html, /not patient-specific doses/);
});

test('components only use utility classes that exist in the design-system Tailwind scale', async () => {
  const { default: config } = await import('../tailwind.config.js');
  const colors = new Set(Object.keys(config.theme.colors));
  const radii = new Set(Object.keys(config.theme.borderRadius));
  const spacing = new Set(Object.keys(config.theme.spacing));
  const fontSizes = new Set(Object.keys(config.theme.fontSize));
  const textKeywords = new Set(['left', 'center', 'right', 'justify', 'start', 'end', 'wrap', 'nowrap', 'balance']);
  const borderKeywords = new Set(['t', 'b', 'l', 'r', 'x', 'y', 'dashed', 'solid', 'dotted', 'none', '0', '2', '4', '8']);
  const problems = [];
  for (const name of ['KnowledgeSection', 'MedicationProfileCard', 'MedicationKnowledge', 'ClinicalAssessment']) {
    const text = await readFile(path.join(src, `${name}.jsx`), 'utf8');
    for (const [, literal] of Array.from(text.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)).map((m) => [m[0], m[1] ?? m[2]])) {
      for (const raw of literal.split(/\s+/).filter((token) => token && !token.includes('${'))) {
        const token = raw.split(':').pop().replace(/\/\d+$/, '');
        let m;
        if ((m = token.match(/^rounded-([a-z0-9]+)$/)) && !radii.has(m[1])) problems.push(`${name}: ${raw}`);
        if ((m = token.match(/^-?(?:p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap|gap-x|gap-y)-(\d+)$/)) && !spacing.has(m[1])) problems.push(`${name}: ${raw}`);
        if ((m = token.match(/^bg-([a-z-]+)$/)) && !colors.has(m[1])) problems.push(`${name}: ${raw}`);
        if ((m = token.match(/^text-([a-z-]+)$/)) && !colors.has(m[1]) && !fontSizes.has(m[1]) && !textKeywords.has(m[1])) problems.push(`${name}: ${raw}`);
        if ((m = token.match(/^border-([a-z-]+)$/)) && !colors.has(m[1]) && !borderKeywords.has(m[1])) problems.push(`${name}: ${raw}`);
      }
    }
  }
  assert.deepEqual(problems, []);
});
