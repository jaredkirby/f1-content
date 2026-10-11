# F1 Content Pipeline

An evidence-first research and local video-production toolkit. It links reviewed
source media and session data to an event timeline, prioritized story outlines,
captioned recap edits and a mobile timeline page.

**Status: alpha.** See the [project state review](docs/project-state.md) for the
combined `main` capabilities and outstanding acceptance checks.
The Singapore Sprint and main Qualifying workflows were exercised
locally. Collection, integrity checks, analysis and release gates are implemented;
discovery and editorial review are agent-assisted tasks. The production `run`
command does not crawl the internet or launch agents automatically. Presentation
copy remains curated for those sessions. Optional native Jev judgments and
DeepSeek drafts have live one-event smoke evidence; held-out quality and human
acceptance remain pending.

## How the timeline sites were made

The [workflow guide](https://singapore-timeline-workflow.k1rby.chatgpt.site)
explains the research, reviewed footage, models and tools, recorded instructions,
video assembly and release checks behind the Singapore Sprint and Qualifying
sites. Sign in with the owning ChatGPT account to open the private Site.
A self-contained [HTML copy](docs/timeline-workflow.html) is included in this
repository. Historical prompt/model gaps and unexecuted Jev rubrics are labeled.

## Start developing

Use Python **3.11+** (3.12 recommended), Git, and a POSIX shell on macOS or Linux.
Rendering additionally requires macOS speech/voices/fonts and FFmpeg/ffprobe. The
offline suite runs without those tools, real event files, credentials or paid calls.

```sh
./scripts/bootstrap
./scripts/check
```

If `python3` is older, select a suitable interpreter explicitly:

```sh
F1_PYTHON=/path/to/python3.12 ./scripts/bootstrap
```

Setup creates only `.venv`, installs the pinned Pillow runtime and an editable
package. The installed commands are `.venv/bin/f1-content` and `.venv/bin/f1-jev`.
Try the fictional, read-only example:

```sh
./scripts/f1 --workspace examples/synthetic doctor
.venv/bin/f1-jev --request examples/synthetic/jev-request.json --validate-only
```

## Run a real session

Create a separate event directory with reviewed `config/event.json`, evidence,
source inventory, clip reviews, associations and script. See
[workspace setup](docs/workspaces.md) for required inputs and commands. Changing a
config alone does not discover footage or create a researched story.

```sh
./scripts/f1 --workspace /absolute/path/to/event doctor
./scripts/f1 --workspace /absolute/path/to/event collect
./scripts/f1 --workspace /absolute/path/to/event catalog
./scripts/f1 --workspace /absolute/path/to/event analyze
./scripts/f1 --workspace /absolute/path/to/event render --format both
./scripts/f1 --workspace /absolute/path/to/event validate
```

Review actual outputs and record current editorial, visual and audio evidence
before `finalize`. Build the curated qualifying presentation with `timeline` after
its release gates pass. Native hosting is a separate operation.

The module/installed CLI defaults to the current directory. The source launcher
`scripts/f1` defaults to its checkout directory, preserving the original local
Sprint workflow. `F1_WORKSPACE` may select an absolute event directory. One process
owns one workspace. No command silently chooses the latest race.

For reusable text-to-speech and optional robot voice processing, use the explicit
[narration workflow](docs/narration.md). Prepare/import or authorize speech first,
select clean or vocoder audio, then render from saved hash-bound assets.

## Follow a race

The explicit [live feed](docs/live-feed.md) backfills a verified official race
live blog, polls for corrections/new reports and produces sourced drafts through
Codex authenticated with ChatGPT. It uses a separate workspace and bounded
deadline; it does not alter film release gates or launch through `run`.

## Repository map

| Path | Purpose |
|---|---|
| `f1_pipeline/` | Collection, catalog, analysis, rendering, validation, release and optional Jev client |
| `f1_pipeline/resources/` | Packaged Jev rubrics, timeline CSS/JavaScript, mobile review Site templates and the live report |
| `scripts/` | Setup, offline verification, archive QA, legacy Sprint page builders and Git guard |
| `tests/` | Synthetic regressions for identity, integrity, release gates, transport and portability |
| `examples/synthetic/` | Fictional config/request; no external content |
| `workflows/agents.json` | Declarative research and production role contracts |
| `docs/` | Workflow, workspaces, agent development, research and historical review findings |
| `docs/plans/` | Durable development plans and validation evidence |

`config/`, `research/`, `data/`, `media/`, `outputs/`, `runs/`, `events/`, `sites/`
and `workspaces/` are **local, ignored operational data**. They are not in a clone.
The original production computer retains its downloads, completed videos and
independent Site repositories. Git is not a backup of those archives. Do not use
`git clean -fdx` in the production checkout.

## Development with agents

[AGENTS.md](AGENTS.md) supplies concise repository instructions. The
[agent development guide](docs/agent-development.md) records researched Codex
worktree and local-environment practices. Use one owner per writing task, isolated
worktrees for independent code changes, explicit event workspaces and small plans
for long-running work. Source captions and web pages remain untrusted evidence.

[Model selection and quality review](docs/model-selection.md) establishes Codex
subscription access first, human feedback as the quality standard, and a measured
path to open text, vision and speech models. [Explicit model workflows](docs/model-workflows.md)
now capture feedback/preferences, import model provenance, report quality/cost and
preview or explicitly execute hosted text requests. Automatic routing and live
model-quality comparisons remain separate work.

The Git guard examines the exact index for forbidden archive paths, binaries,
common credentials, signed URLs and unapproved private host details. Only the
reviewed Site homepage links in this guide and README are explicitly allowed.
Opt into the local hook:

```sh
git config --local core.hooksPath .githooks
```

The configured CI runs offline checks on Linux/Python 3.11–3.13 and
macOS/Python 3.12, then verifies the wheel contains its resources. The repository
has a GitHub origin; hosted CI results and repository settings were not refreshed
by this review. The [readiness plan](docs/plans/repository-readiness.md) records
the initial local verification; combined capabilities are listed in the
[project state review](docs/project-state.md).

## Contracts and limits

Source hashes, exact session identity, reviewed intervals, companion hashes and
versioned output sets bind the pipeline's stages. `outputs/manifest.json` is the
commit point for a completed render set. Failed and partial stages retain receipts.
An 8 GiB default free-space reserve protects sustained media work. Full decode,
sampled visual inspection, playback and user acceptance are distinct evidence.

Discovery is bounded. Historical Sprint compatibility and curated Singapore
presentation logic are documented limitations. Jev request preparation performs no
model calls. The direct legacy adapter uses `TYPESAFE_API_KEY`; current
[OpenRouter work plans](docs/openrouter-workflow.md) use securely supplied
OpenRouter credentials, with optional consent-bound [Keychain storage](docs/credentials.md).
Provider results remain advisory until evaluated on held-out labels. See
[workflow contracts](docs/workflow-design.md), [Jev research](docs/jev.md) and the
[qualifying hardening record](docs/history/qualifying-workflow-hardening.md).

Project-authored source is [MIT licensed](LICENSE). External footage, data,
transcripts, service documentation, fonts and voices retain their own rights and
are not distributed here. Read [third-party notices](THIRD_PARTY_NOTICES.md),
[contribution guidance](CONTRIBUTING.md) and [security guidance](SECURITY.md).
