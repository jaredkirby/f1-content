# Timeline workflow explainer

Status: complete

## Objective

Generate a standalone local HTML page explaining the retained Singapore Sprint
and main Qualifying timelines, using their monochrome styling and phone layout.

## Decisions

- Inspect local workflow contracts, source, delivery and Site QA records.
- Separate recorded role instructions from unavailable historical chat prompts,
  prepared-but-unexecuted Jev rubrics and a newly written reusable brief.
- Do not infer historical model identity from the saved Codex default. Keep later
  hosted-model candidates separate from production of the original timelines.
- Keep the generated page and private verification evidence in ignored local
  data. No source-media copy, event rerun or model provider request.
- The follow-up request for a Sites link authorizes private publication of this
  guide. Keep its Site source repository separate from the pipeline repository.
- The request to save and commit the guide authorizes its HTML documentation copy
  and a README entry linking both that copy and the hosted guide. Allow only those
  exact homepage URLs in the relevant files; keep other guard checks intact.

## Next action

The standalone guide is saved at `docs/timeline-workflow.html`; the README links
both the source copy and hosted guide. Commit only this task's reviewed files.
Native deployment returned `succeeded`; the independent Site source and private
receipt remain in ignored local storage, separate from the committed guide.

## Verification

Passed unique IDs, all internal anchors, self-contained resource checks and
JavaScript syntax. Browser inspection at 320, 390, 768 and 1280 px found no page
overflow. Verified session switching, stage expansion, prompt filtering/copy,
themes, theme persistence after reload and mobile navigation; no console errors
or warnings. Saved phone and desktop screenshots. Private publication succeeded
through the native Sites workflow; evidence is in the ignored QA directory.
The committed HTML matches the deployed Site source byte-for-byte. All 49 IDs
are unique; its anchors, README file links and JavaScript syntax pass. Guard
regressions pass for exact allowed homepage/file pairs and reject URL paths,
queries, lookalike hostnames, wrong files and credentials. `scripts/check` passed
the offline suite, synthetic CLI/adapter smoke checks, index and diff checks.
Only the guide, README, security note, guard/tests and this plan are staged;
unrelated timeline resource edits and their plan remain outside this commit.
Original films/hosted sites and human phone acceptance were not retested.
