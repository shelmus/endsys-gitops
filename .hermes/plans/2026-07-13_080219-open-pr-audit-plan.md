# Open pull-request audit and update plan

Created: 2026-07-13 08:02 EDT
Repository: `shelmus/endsys-gitops`
Scope: all 36 pull requests open at inventory time (#218–#286, non-contiguous)

## Safety boundary

- Read-only GitHub, repository, and cluster inspection is authorized.
- Repo-local edits, validation, and commits on pull-request branches are in scope when a verified defect requires them.
- Ahead-only pushes to Sean-owned feature/renovate branches are allowed after green verification and will be reported.
- No pull-request merges, closes, reviews, approvals, comments, workflow reruns, Flux reconciliations, or live cluster changes without an explicit red-gate approval.

## Work

1. Inventory every open PR, its diff, author, branch, CI, mergeability, and distance from `main`.
2. Check upstream release and migration notes, deployed versions, and cross-PR sequencing.
3. Classify each PR as READY, HOLD, SUPERSEDED/CLOSE, or NEEDS CHANGE.
4. Make only verified branch-local fixes; validate render/schema and push only ahead-only commits.
5. Record exact evidence and any red-gate commands still awaiting approval in `.hermes/ledger/`.

## Verification

- GitHub checks and merge state for each PR.
- `git diff --check` for each PR diff.
- Flux-local CI evidence for Kubernetes changes.
- Local `kubectl kustomize` / schema or targeted commands where available.
- Read-only live-cluster compatibility checks for current Kubernetes, Talos, Flux, CRDs, and installed workloads.
