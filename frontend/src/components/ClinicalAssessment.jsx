const DOMAIN_LABELS = {
  drug_food_interactions: 'Drug–food interactions',
  contraindications: 'Contraindications',
  dosage_references: 'Dosage references',
  administration_instructions: 'Administration instructions',
};

const STATUS_LABELS = {
  context_not_supplied: 'Not evaluated — context not supplied',
  no_approved_assertions: 'No approved assertions available',
  approved_findings_present: 'Approved findings available',
  no_matching_approved_assertion: 'No matching approved assertion found',
};

export default function ClinicalAssessment({ assessment }) {
  if (!assessment) return null;
  const findings = assessment.findings ?? [];
  const domains = assessment.domains ?? {};
  const conflicts = assessment.unresolved_conflicts ?? [];

  return (
    <section className="rounded-xl border border-fog p-24" aria-labelledby="clinical-assessment-heading">
      <h3 id="clinical-assessment-heading" className="font-clarkson text-body-sm text-obsidian">Clinical evidence assessment</h3>
      <p className="mt-8 font-clarkson text-caption leading-relaxed text-slate">
        This assessment uses only explicitly approved assertions with an acceptable conflict review. Missing knowledge is not evidence of safety.
      </p>
      <ul className="mt-16 flex flex-col gap-12">
        {Object.entries(domains).map(([domain, detail]) => (
          <li key={domain} className="border-t border-fog pt-12 first:border-t-0 first:pt-0">
            <p className="font-clarkson text-body-sm text-obsidian">{DOMAIN_LABELS[domain] ?? domain}</p>
            <p className="mt-4 font-clarkson text-caption text-slate">{STATUS_LABELS[detail.status] ?? detail.status}</p>
            <p className="mt-4 font-clarkson text-caption text-slate">{detail.approved_assertions_available} approved · {detail.excluded_unapproved_or_conflicted} excluded</p>
          </li>
        ))}
      </ul>
      {findings.length > 0 && (
        <div className="mt-16 border-t border-fog pt-16">
          <p className="font-clarkson text-body-sm text-obsidian">Evidence-backed findings</p>
          <ul className="mt-8 flex flex-col gap-12">
            {findings.map((finding) => (
              <li key={finding.assertion_id} className="rounded-lg bg-fog p-12">
                <p className="font-clarkson text-body-sm text-obsidian">{finding.medication} · {finding.domain.replaceAll('_', ' ')}</p>
                <p className="mt-4 font-clarkson text-caption text-ash">{finding.message}</p>
                <p className="mt-4 font-clarkson text-caption text-slate">{finding.assertion_id} · {finding.source} · {finding.evidence_strength} evidence</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {conflicts.length > 0 && (
        <p className="mt-16 rounded-lg border border-dashed border-slate p-12 font-clarkson text-caption text-obsidian" role="alert">
          {conflicts.length} assertion(s) have unresolved conflicting evidence and were excluded from reasoning.
        </p>
      )}
      <div className="mt-16 border-t border-fog pt-16">
        <p className="font-clarkson text-caption text-obsidian">Dosage safety: {assessment.dosage_safety?.message}</p>
        <p className="mt-8 font-clarkson text-caption text-slate">{assessment.interpretation}</p>
        <p className="mt-8 font-clarkson text-caption font-semibold text-obsidian">Not for diagnosis, prescribing, or independent medication changes. Clinical use is not permitted.</p>
      </div>
    </section>
  );
}
