# Mobile video and feedback destination

Date: 2026-10-10. Status: implemented and privately published; latest-version
hosted playback/authentication follow-through passed on 11 October.

Current follow-up: the latest 41.3-second edit is published and remains unreviewed
in saved evidence. The [remaining-work plan](remaining-implementation.md) tracks
the separate credential-template rollout. Current hosted playback/authentication
checks passed for the latest film; actual phone feedback remains pending.

## Objective

Publish a private mobile destination for the exact 46.8-second pilot, with
timestamped annotations, approve/reject comments and a clear path to feedback in
the existing chat. Make this web destination part of early pilot testing.

## Decisions

- Use a new private Site; preserve the independent existing event Sites.
- Keep the video primary, with accessible controls outside the picture so they
  do not obscure burned captions. One output at a time; no automatic A/B choice.
- Use Sites sign-in and durable D1 feedback. Bind every record to the exact event,
  manifest/video/model-receipt version; server validates against current content.
- Notes and decisions are append-only. Store only explicit feedback, not passive
  playback analytics or inferred taste. Preserve text and timestamp context.
- Chat remains an equally valid review path. A copy-for-chat action includes the
  reviewed pilot/moment without adding another chatbot or model API.
- Persist the Site destination/version and actual browser checks in the private
  pilot workspace. Future pilots require a current mobile destination and checks
  before feedback handoff, with no publishing implied by offline regression tests.

## Verification

Test phone/tablet widths, real video load/play/pause/seek, caption visibility,
timestamped note capture, saved feedback after reload, approve/reject flow, stale
version rejection and authenticated durable storage. Use local synthetic feedback
for browser tests; production records remain human-sourced. Check the deployed
private page/media and preserve native deployment evidence. Shared source changes
receive relevant regressions, then `scripts/check` before commit.

## Next action

The human opens the private destination on their phone, verifies sign-in and
submits feedback there or in this chat. Capture that real feedback before changing
important preferences or promoting a model. The latest film's readiness now passes
with current hosted browser evidence; historical sign-in failures stay in their
original receipts.

## Implementation evidence

The reusable Site source uses the supplied Vinext starter, ChatGPT identity and
D1. The offline preparation command binds validated assets and the status command
fails closed until current browser and private deployment evidence agree. Local
browser tests have verified real playback, seek, timestamped annotation persistence,
decision revisions/history and chat copy. Local API checks reject anonymous,
stale, out-of-bounds, forged-identity and cross-origin writes, and preserve retries.
Native private publication succeeded for the exact pushed source. Hosted video
and poster returned 200 with the exact original hashes, and production D1 has
the feedback schema with zero synthetic rows. The preview browser's OpenAI sign-in
failed twice with an expired session (`invalid_state`); no authentication was
weakened. That original receipt kept hosted interaction pending; the latest-film
follow-through above subsequently passed readiness. Shared checks at this original
checkpoint passed: 140 offline regressions,
synthetic CLI smoke/index guard, Site TypeScript/build and local API/browser checks.
