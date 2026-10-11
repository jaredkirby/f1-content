import { and, desc, eq } from "drizzle-orm";
import { z } from "zod";
import { getChatGPTUser } from "@/app/chatgpt-auth";
import { getDb } from "@/db";
import { reviewFeedback } from "@/db/schema";
import pilot from "@/app/data/pilot.json";

export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };
const respond = (data: unknown, status = 200) => Response.json(data, { status, headers });
const inputSchema = z.object({
  requestId: z.string().uuid(),
  manifestSha256: z.string(), videoSha256: z.string(),
  kind: z.enum(["annotation", "decision"]),
  outcome: z.enum(["approved", "rejected"]).nullable(),
  comment: z.string().max(4000),
  timeSec: z.number().finite().min(0).max(pilot.duration).nullable(),
}).strict().superRefine((value, context) => {
  if ((value.kind === "annotation" && (!value.comment.trim() || value.outcome !== null)) ||
      (value.kind === "decision" && (!value.outcome || value.timeSec !== null))) {
    context.addIssue({ code: "custom", message: "Invalid note or decision" });
  }
});
const publicRecord = (record: typeof reviewFeedback.$inferSelect) => ({
  id: record.id, kind: record.kind, outcome: record.outcome, comment: record.comment,
  timeSec: record.timeSec, createdAt: record.createdAt, eventId: record.eventId,
  manifestSha256: record.manifestSha256, videoSha256: record.videoSha256,
  videoVersion: record.videoVersion, modelReceipts: JSON.parse(record.modelReceipts),
});

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return respond({ error: "Sign in to read your feedback." }, 401);
  const db = getDb();
  const current = and(eq(reviewFeedback.userId, user.userId), eq(reviewFeedback.manifestSha256, pilot.manifestSha256));
  const items = await db.select().from(reviewFeedback).where(current).orderBy(desc(reviewFeedback.createdAt), desc(reviewFeedback.id)).limit(200);
  const decisions = await db.select().from(reviewFeedback).where(and(current, eq(reviewFeedback.kind, "decision"))).orderBy(desc(reviewFeedback.createdAt), desc(reviewFeedback.id)).limit(1);
  return respond({ items: items.map(publicRecord), decision: decisions[0] ? publicRecord(decisions[0]) : null });
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return respond({ error: "Sign in to save feedback." }, 401);
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) return respond({ error: "Open this review page to save feedback." }, 403);
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > 20000) return respond({ error: "This note is too long." }, 413);
  let body: unknown;
  try { body = JSON.parse(raw); } catch { return respond({ error: "Invalid feedback." }, 400); }
  const parsed = inputSchema.safeParse(body);
  if (!parsed.success) return respond({ error: "Check the note, timestamp and decision." }, 400);
  const input = parsed.data;
  if (input.manifestSha256 !== pilot.manifestSha256 || input.videoSha256 !== pilot.videoSha256)
    return respond({ error: "This video has changed. Reload before reviewing it." }, 409);
  const db = getDb();
  const query = and(eq(reviewFeedback.userId, user.userId), eq(reviewFeedback.requestId, input.requestId));
  const matches = (record: typeof reviewFeedback.$inferSelect) => record.kind === input.kind &&
    record.outcome === input.outcome && record.comment === input.comment && record.timeSec === input.timeSec &&
    record.manifestSha256 === pilot.manifestSha256 && record.videoSha256 === pilot.videoSha256;
  const existing = (await db.select().from(reviewFeedback).where(query).limit(1))[0];
  if (existing) return matches(existing) ? respond({ item: publicRecord(existing) }) : respond({ error: "A different note used this save request." }, 409);
  const record: typeof reviewFeedback.$inferInsert = {
    id: crypto.randomUUID(), userId: user.userId, requestId: input.requestId,
    kind: input.kind, outcome: input.outcome, comment: input.comment, timeSec: input.timeSec,
    eventId: pilot.eventId, manifestSha256: pilot.manifestSha256, videoSha256: pilot.videoSha256,
    videoVersion: pilot.version, modelReceipts: JSON.stringify(pilot.modelReceipts), createdAt: new Date().toISOString(),
  };
  // A repeated request can race; the unique index prevents duplicate feedback.
  await db.insert(reviewFeedback).values(record).onConflictDoNothing();
  const saved = (await db.select().from(reviewFeedback).where(query).limit(1))[0];
  if (!saved || !matches(saved)) return respond({ error: "This note could not be saved. Please retry." }, 409);
  return respond({ item: publicRecord(saved) }, 201);
}
