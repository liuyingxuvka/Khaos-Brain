---
name: organization-review
description: Review Khaos Brain organization KB maintenance proposals, including card-and-Skill bundles, shared Skill safety, evidence quality, privacy boundaries, and GitHub auto-merge readiness. Use as a review lens for approving, rejecting, merging, splitting, or promoting organization KB candidates or organization Skill registry changes.
---

# Organization Review

Use this Skill when reviewing organization KB changes or running full
organization maintenance automation. It is guidance for judgment, not a hard
apply gate for ordinary organization Sleep maintenance.

## Review Contract

Treat the review unit as a bundle, not a standalone file:

- import candidate, `main` card change, or Skill-linked card bundle;
- declared Skill dependency or Skill registry change;
- task evidence and provenance;
- privacy and sharing policy impact;
- GitHub merge path and rollback story.

Do not approve a Skill only because it exists. A Skill becomes organization
knowledge only when cards explain when it is useful, what outcome it predicts,
what fallback exists, and what evidence supports it.

Treat the organization KB as a shared exchange layer, not as a central truth
layer. Organization `main` cards may be maintained with the same
editorial posture as local Sleep: keep, reject, watch, merge, split, rewrite,
promote, demote, deprecate, or cross-link when evidence supports the decision.
Do not reject a card-content change merely because the target is already in `main` or already trusted;
instead review the evidence, privacy boundary, usefulness, and rollback story.

## Required Checks

1. Validate the organization repository manifest and expected paths.
2. Confirm changed paths match the intended merge lane.
3. Reject raw private preferences, credentials, tokens, local absolute paths,
   hardware identifiers, or user-specific interaction memories.
4. For cards, check that scenario, action, prediction, confidence, route, and
   operational use are organization-reusable.
5. For Skill dependencies, check that each dependency is required, recommended,
   or optional and has evidence from one or more cards.
6. For card-bound Skill bundles, require `bundle_id`, `content_hash`,
   `version_time`, `original_author`, read-only import behavior, and
   `update_policy: original_author_only`.
7. For same-`bundle_id` updates, approve only original-author updates and use
   `version_time` to select the latest approved version; non-author changes
   must fork to a new `bundle_id`.
8. For approved Skills, require a pinned version or version time and `sha256:`
   content hash.
9. Do not auto-install or recommend auto-install for `candidate`, `rejected`,
   unknown, or unpinned Skills.
10. Treat `main` card content maintenance as in scope for organization Sleep
    when evidence supports it. Keep privacy, registry, policy, organization-review
    Skill changes, and executable Skill changes under stricter review.
11. Record rejection reasons when a bundle is weak, unsafe, private, too local,
   duplicated, or missing evidence.
12. Keep the output reviewable: summarize accepted changes, rejected changes,
    unresolved risks, checks run, and the exact GitHub branch or PR path.

## Decision Labels

- `candidate`: unreviewed or still gathering evidence.
- `approved`: reviewed with sufficient card evidence and safe install metadata.
- `rejected`: reviewed and not recommended; keep the reason as an audit signal.

Avoid inventing additional first-pass states unless repository policy has been
updated to support them.
