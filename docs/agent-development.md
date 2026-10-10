# Agent development and Codex workspace practices

Research checked 2026-10-10 against official documentation. The decisions below
apply to this repository; they do not change anyone's global Codex preferences.

## Applied research

| Official source | Relevant guidance | Application here |
|---|---|---|
| [OpenAI: AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Project instructions are discovered from the Git root toward the working directory; narrower instructions take precedence | A concise root file provides commands and source/archive boundaries. Detailed workflow material stays in linked docs |
| [OpenAI: instruction and skill design](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) | Keep instructions scoped and use progressive disclosure; avoid unnecessary recipes and context | No bundle of overlapping repo skills or model-specific prompt stack. Read the relevant guide only when the task needs it |
| [OpenAI: Git worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees) | Independent chats can use separate checkouts; managed worktrees are disposable and share Git metadata | Independent code changes use separate worktrees. Real media stays in durable event storage; never copy it or secrets through `.worktreeinclude` |
| [OpenAI: local environments](https://learn.chatgpt.com/docs/environments/local-environment) | App settings configure worktree setup scripts and common actions; the app generates shareable configuration | `scripts/bootstrap` and `scripts/check` are the stable setup/action commands. Generate app configuration through Settings when adopting it, rather than guessing its schema |
| [OpenAI: long-running plans](https://developers.openai.com/cookbook/articles/codex_exec_plans) | A durable plan lets later sessions understand objective, decisions and progress | Substantial changes use short `docs/plans/` records. Runtime receipts and private URLs stay in ignored workspaces |
| [GitHub: secure Actions](https://docs.github.com/en/actions/reference/security/secure-use) | Pin actions to full commit SHAs, use minimal token permissions and avoid untrusted jobs on self-hosted runners | CI uses verified upstream pins, `contents: read`, no persisted checkout credential, time limits and ephemeral hosted runners |

Action pins were resolved against `actions/checkout` v7.0.1 and
`actions/setup-python` v7.0.0 using their official GitHub release/ref APIs.
Dependabot is configured to propose updates. Pins improve reproducibility; they
do not substitute for reviewing dependency changes.

## Local and worktree setup

Open the repository root as the Codex project. Keep the media production checkout
durable. New code tasks can use the app's **Worktree** environment after a first
commit exists. The app-managed checkout may start detached; create a branch there
when preparing a lasting change. Use the app's Handoff workflow when moving a task
between its local checkout and worktree; do not force the same branch into both.

In the app's local environment settings, use `./scripts/bootstrap` as the setup
script and `./scripts/check` as a **Check** action. A **Doctor (synthetic)** action
can run `./scripts/f1 --workspace examples/synthetic doctor`. Setup installs Python
dependencies and therefore needs package-index access; tests themselves are offline.
Choose a Python 3.11+ executable with `F1_PYTHON` on hosts whose default is older.
The shell recipes are tested independently of the desktop UI. No global model,
permission policy, automation or app-generated environment file is installed by
this repository preparation.

Ignored production files are intentionally missing from new worktrees. Develop
against synthetic fixtures. If a task requires real event execution, select a
durable workspace explicitly and ensure only one writer owns it. Do not copy a
working `.venv` between checkouts; bootstrap each environment. An event workspace
must not live in an automatically deleted worktree.

## Task and handoff contract

State the intended behavior, acceptance criteria and boundaries in the task.
Keep a plan for substantial work. When parallel agents are requested, assign
non-overlapping file ownership or separate worktrees; research can run independently
of code changes. A shared checkout means shared files, not isolation. One owner
integrates, resolves conflicts, stages and commits. Delegates return paths, changes,
checks performed and unresolved questions.

Use the app's review panel or `git diff` to inspect the final implementation.
Verify changed behavior with meaningful regressions, then run the shared check
once. Do not repeatedly rerun identical tests without new changes or uncertainty.
Record actual results, including unavailable platform tools. A successful unit
suite cannot prove an edited film is legible, audible or publishable.

## Package verification

```sh
.venv/bin/python -m pip wheel --no-deps --wheel-dir dist .
.venv/bin/python scripts/check_wheel.py dist/*.whl
```

For a release, install that wheel in a new temporary environment, change to a
directory outside the checkout, and run the installed CLI against the synthetic
workspace. Confirm packaged CSS, JavaScript and Jev rubrics can be loaded there.
This catches accidental reliance on ignored research files or editable-install
paths. Review both the Git index and wheel contents before release.

The complete release smoke check is reusable after committing source changes:

```sh
.venv/bin/python scripts/check_clean_clone.py
```

It clones committed `HEAD` into a disposable directory, installs dependencies,
runs the offline suite, builds a wheel and installs it into another fresh
environment. Installed commands and Jev request preparation run outside the source
checkout using fictional evidence, with no inference. It needs package-index
access, removes its temporary environments and retains logs under ignored
`runs/source-verification/`. It refuses a dirty source tree to make the tested
revision unambiguous.

## Event archive boundaries

This checkout contains ignored production archives and nested Site Git repositories.
Before operations that could affect them, record exact file hashes and each Site's
HEAD/status in `runs/`. Compare afterward. Do not move nested repositories into the
parent index as gitlinks. Backup/retention and source version control are separate
responsibilities. Local-only details are discoverable from the archive itself;
they should not be copied into public development instructions.
