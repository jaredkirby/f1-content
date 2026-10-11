# Mobile review Site source

These authored files overlay the supplied Sites Vinext starter. The independent
Site checkout, generated migration history, dependencies and media stay ignored.
Use `prepare-review-site` from one explicit event workspace to copy the exact
validated video, poster, narration and captions plus this application source.
The command preserves the starter's auth/build integration and Site project ID.
It never publishes or records approval. See [mobile review workflow](../../docs/mobile-review.md).

The server binds append-only notes and decisions to the signed-in Sites user,
manifest/video hashes and model receipts. An annotation does not reset a decision;
the latest explicit approval/rejection governs. Request IDs make retries idempotent.
No passive playback analytics or inferred preferences are collected.

For a new checkout, generate and inspect schema-only Drizzle migrations, build,
apply pending SQL to local D1, then test in the supplied local sign-in preview.
Do not replay applied migrations. Run `tsc --noEmit`, the actual browser workflow
and `node scripts/verify-feedback.mjs http://127.0.0.1:5173`. That script refuses
hosted origins and submits only clearly marked local synthetic records.

Publish the exact pushed source through the Sites skill to the existing private
audience. Do not upload local test data. Hosted D1 is separate. Review and preserve
generated SQL/Drizzle metadata in that Site's independent source repository.

The `/connect` page is a temporary mobile credential handoff, independent of
feedback. Keys are AES-GCM encrypted with native runtime secrets, scoped to the
current authorized operation and collected once. Never log plaintext or put
secrets in browser storage/source. Test with `node --experimental-strip-types
--test scripts/test-credential-box.mjs`, then local HTTP/browser checks with
synthetic keys. Configure production values only through native Sites settings.
