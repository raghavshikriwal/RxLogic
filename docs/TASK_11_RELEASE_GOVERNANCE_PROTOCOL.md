# Task 11 — Release Governance and Dual-Control Protocol

## Purpose and scope

Task 11 strengthens the existing immutable knowledge-release lifecycle. Tasks 06–10 already provide evidence ingestion/review, candidate curation, candidate-level clinical approval, immutable release manifests, explicit promotion, rollback, and a promotion-event hash chain. Task 11 adds an independent release-level approval gate and binds that review state to runtime activation.

This is a software governance control. It does not prove clinical correctness, authenticate a reviewer, verify professional credentials, or authorize patient-care use.

## Release lifecycle

```text
Accepted evidence
      |
      v
Evidence-backed candidate
      |
      v
Independent candidate clinical approval
      |
      v
Immutable release assembly
      |
      v
Release-level clinical review
      |
      v
Release-level governance review
      |
      v
Independent steward/administrator promotion
      |
      v
Active pointer + committed audit event
      |
      v
Runtime verifies manifest, datasets, promotion chain,
release-review chain, and bound review digest
```

Release creation remains separate from activation. A newly created release is pending release-level review and cannot be promoted immediately.

## Required release reviews

| Review type | Allowed declared role | Minimum approvals |
|---|---|---:|
| `clinical_release` | `clinical_pharmacist` or `physician` | 1 |
| `governance_release` | `knowledge_steward` or `administrator` | 1 |

A rejection in the latest decision state blocks promotion. The same reviewer may later append a new decision with a rationale; the earlier rejection remains in the audit history.

## Separation of duties

- The release creator cannot review that release.
- Candidate authors cannot perform release-level review.
- Candidate-level clinical approvers cannot perform release-level review.
- The clinical-release and governance-release reviewers must be different identities.
- A promoter must differ from the release creator, candidate authors, candidate-level clinical approvers, and both release reviewers.
- A release's review record cannot be changed while that release is active.
- Rollback requires a non-empty rationale, a previously completed promotion, current candidate approval/evidence eligibility, current dual-control review, and an independent rollback actor.

Identity comparisons are case-insensitive on the declared ID strings. The local CLI does not authenticate those IDs or role declarations.

## Integrity and runtime binding

`knowledge/release_review_events.jsonl` is append-only under the application code and protected by a SHA-256 hash chain. Each review event records:

- Release ID.
- Raw SHA-256 digest of the immutable `manifest.json` bytes.
- Review type and decision.
- Reviewer ID and declared role.
- UTC timestamp and rationale.
- Previous event digest and current event digest.

The promotion/rollback pointer stores a digest over all review-event hashes for that release. The promotion intent and completion events include the same digest. Runtime rejects the active release if the manifest, promotion chain, review chain, dual approvals, or bound review digest no longer verifies.

SHA-256 provides tamper evidence relative to the local log. It is not a digital signature, external timestamp, or protection against a privileged attacker who can rewrite all files and recompute the chain.

## CLI workflow

All commands run from the repository root. The global path overrides must precede the subcommand.

```powershell
# Create an immutable release from already approved candidates.
python -m scripts.manage_knowledge create CANDIDATE-ID --actor-id release-builder-01 --rationale "Release preparation rationale"

# Record clinical release review.
python -m scripts.manage_knowledge release-review RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX --reviewer-id clinical-reviewer-01 --reviewer-role clinical_pharmacist --review-type clinical_release --decision approved --rationale "Release-level clinical review rationale"

# Record separate governance release review.
python -m scripts.manage_knowledge release-review RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX --reviewer-id governance-reviewer-01 --reviewer-role knowledge_steward --review-type governance_release --decision approved --rationale "Release governance review rationale"

# Inspect current review state before promotion.
python -m scripts.manage_knowledge review-status RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX

# A third, independent actor promotes the release.
python -m scripts.manage_knowledge promote RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX --actor-id independent-promoter-01 --actor-role administrator

# Rollback requires a previously promoted/reviewed release and an explicit reason.
python -m scripts.manage_knowledge rollback RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX --actor-id independent-rollbacker-01 --actor-role administrator --rationale "Documented rollback reason"

# Run the Task 11 governance audit.
python -m scripts.audit_task11 --output reports/task11_acceptance_audit.json
```

The identifiers above are examples only. No reviewer identities, real approvals, or clinical assertions are supplied by Task 11.

## Legacy release behavior

Older Task 06–10 release bundles remain inspectable when their existing manifest and dataset hashes validate. They lack Task 11 governance context and cannot be newly reviewed, promoted, rolled back to, or loaded as an active runtime release under the new dual-control policy. Rebuild a release from currently eligible candidates, record new release-level reviews, then promote it. Do not hand-edit older manifests or pointers to bypass this gate.

An already active pre-Task-11 pointer will fail closed after the Task 11 loader is installed. Preserve all old files and perform a controlled, documented rebuild/review before enabling active-release mode again.

## Audit interpretation

The Task 11 audit checks the policy file, release manifests/datasets, release-review hash chain, release-review states, and active runtime behavior. A clean audit does not mean clinical validation passed. If no release is active, the expected result is that runtime refuses legacy/unreviewed fallback.

## Security and deployment limitations

- Local actor IDs and role strings are declarations, not authentication or credential verification.
- CLI operations require host-level access controls; do not expose release mutations through anonymous HTTP endpoints.
- The local JSON/JSONL files are not a multi-host database or distributed transaction manager. Serialize governance writes.
- Protect the knowledge directory, backups, deployment host, and audit logs with operating-system permissions and monitored access.
- Production use would require authenticated identities, authorization, signed/external audit anchoring, backup/restore procedures, operational monitoring, clinical validation, and applicable regulatory/privacy review.
- `clinical_use_permitted` remains `false`.
