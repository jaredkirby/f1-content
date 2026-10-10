# Contributing

Start with [README.md](README.md), create a branch or worktree, and run
`scripts/bootstrap`. Contributions should solve a concrete problem with a small
reviewable change. Discuss large new providers or workflow changes before building
them. Treat contributors respectfully; criticize code and evidence, not people.

Use temporary synthetic fixtures for regressions. Do not download race footage,
invoke models or access real credentials in tests. A behavioral fix should include
a regression that would have failed before the fix. `scripts/check` is the shared
local/CI command. Changes to packaging also need a wheel build and installed-wheel
smoke test; see [agent development](docs/agent-development.md).

Review `git diff`, stage explicit paths, run `scripts/repo_guard.py`, and review
`git diff --cached` before committing. An optional local hook is provided:

```sh
git config --local core.hooksPath .githooks
```

Hooks are opt-in in each clone and do not replace CI. Do not force-add ignored
files to work around the guard. If a new source directory is legitimate, update
the guard policy and its tests in the same review.

Describe the problem and resulting behavior in the pull request. Include executed
checks and limits. Separate technical decode checks, sampled visual inspection,
full playback and user acceptance. New media, data and model integrations must
preserve provenance and distinguish an implemented client from a verified live run.

By submitting project-authored changes, you agree to contribute them under the
[MIT license](LICENSE). Only submit material you have the right to contribute.
Downloaded footage, transcripts, provider documentation and private event archives
do not become MIT-licensed through this repository.
