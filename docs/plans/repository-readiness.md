# Repository readiness

Date: 2026-10-10. Status: implemented; final clean-clone verification pending.

## Objective

Turn the local F1 production prototype into a portable, reviewable source repository
that people and coding agents can develop without access to private event archives.
Preserve completed Singapore deliveries and their independent Site repositories.

## Assessment

- No root Git history or package metadata; two nested Site checkouts already exist.
- Code and event evidence share a directory. Discovery records can contain signed
  URLs; original footage, provider receipts and hosting metadata are not source.
- Baseline: 63 pipeline tests and 9 offline Jev contract tests pass on Python 3.12.
- The launcher assumes one Mac runtime; Jev and timeline resources live outside
  the package. Fresh installations need an explicit workspace and useful diagnostics.
- Existing release gates already check hashes, exact session identity, reviewed
  intervals and complete output sets. Preserve those contracts during organization.

## Implementation plan

1. Establish ignored archive boundaries and snapshot retained delivery hashes.
2. Package shared code/resources, make setup portable, consolidate offline tests,
   and supply synthetic examples independent of the retained event data.
3. Document architecture, agent/worktree practice, contribution and licensing;
   record official research sources and concrete decisions.
4. Add staged-file publication checks, opt-in hooks and least-privilege CI.
5. Test a clean source checkout and wheel, verify archive preservation, review the
   exact index, initialize `main`, and commit the complete source tree.

## Validation and handoff

Implemented the source/archive boundary, portable Python package and CLI, bundled
resources, 78 consolidated offline tests, synthetic examples, developer/agent docs,
MIT licensing, contribution/security guidance, a staged-blob guard, local hook and
SHA-pinned CI. Existing delivery archives and one-off research scripts remain local.

Verified so far: `scripts/bootstrap`, `scripts/check`, both retained workspaces'
read-only `doctor`, shell syntax, Markdown links, dependency consistency and a
26-file wheel containing the required rubrics/CSS/JavaScript. The source index has
67 files, approximately 410 KB, with no forbidden guard matches. CI configuration
has not run on hosted Linux/macOS runners yet.

The first clean-clone run exposed a real fixture isolation bug: an older render
test patched only the renderer workspace while the validation helper read the
production config. The test now uses the complete shared synthetic fixture and
asserts the intended identity error. `scripts/check` also assigns an empty
temporary default workspace, so accidental archive reads fail locally. The 78
tests pass with that isolation. `scripts/check_clean_clone.py` makes the complete
clone/install verification reusable.

Next: commit the isolation fix, repeat clean-clone and installed-wheel checks,
then record the results. All 40 retained media hashes and both Site HEAD/status
snapshots match the pre-change snapshot.
No remote publication is part of this preparation. Live provider inference, new
downloads, final renders and hosting are not needed to validate source readiness.
