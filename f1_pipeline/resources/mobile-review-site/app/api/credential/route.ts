import { env } from "cloudflare:workers";
import { and, desc, eq, lte } from "drizzle-orm";
import { z } from "zod";
import { getChatGPTUser } from "@/app/chatgpt-auth";
import { getDb } from "@/db";
import { mobileCredentials } from "@/db/schema";
import { HANDOFF_TTL_MS, sealKey, openKey } from "@/lib/credential-box";
import { readBoundedBody } from "@/lib/bounded-body";
import { matchesStorageOperation } from "@/lib/credential-operation.mjs";
import operation from "@/app/data/credential-operation.json";

export const dynamic = "force-dynamic";
const respond = (data: unknown, status = 200) => Response.json(data, { status,
  headers: { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } });
const schema = z.object({ operationId: z.string(), persistKeychain: z.boolean(), requestId: z.string().uuid(),
  key: z.string().trim().min(1).max(512).regex(/^[!-~]+$/) }).strict();
const publicRecord = (row: typeof mobileCredentials.$inferSelect) => ({
  id: row.id, status: row.status, expiresAt: row.expiresAt, createdAt: row.createdAt,
});
async function expireHandoffs() {
  await getDb().update(mobileCredentials).set({ status: "expired", ciphertext: null, iv: null })
    .where(and(eq(mobileCredentials.status, "pending"), lte(mobileCredentials.expiresAt, Date.now())));
}
export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return respond({ error: "Sign in to enter your key." }, 401);
  await expireHandoffs();
  const rows = await getDb().select().from(mobileCredentials)
    .where(and(eq(mobileCredentials.userId, user.userId), eq(mobileCredentials.operationId, operation.id)))
    .orderBy(desc(mobileCredentials.createdAt)).limit(1);
  return respond({ item: rows[0] ? publicRecord(rows[0]) : null,
    ready: operation.enabled && matchesStorageOperation(operation, {operationId: operation.id, persistKeychain: operation.persistKeychain}) && !!env.MOBILE_CREDENTIAL_ENCRYPTION_KEY && !!env.MOBILE_CREDENTIAL_OPERATOR_TOKEN });
}
export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return respond({ error: "Sign in to enter your key." }, 401);
  if (!operation.enabled || !env.MOBILE_CREDENTIAL_ENCRYPTION_KEY || !env.MOBILE_CREDENTIAL_OPERATOR_TOKEN)
    return respond({ error: "The private key handoff is not ready yet." }, 503);
  const origin = request.headers.get("origin");
  if (!origin || origin !== new URL(request.url).origin) return respond({ error: "Open this page to send your key." }, 403);
  let raw: string;
  try { raw = await readBoundedBody(request, 4096); }
  catch { return respond({ error: "Invalid key submission." }, 413); }
  let input: unknown;
  try { input = JSON.parse(raw); } catch { return respond({ error: "Invalid key submission." }, 400); }
  const parsed = schema.safeParse(input);
  if (!parsed.success) return respond({ error: "Paste the complete key without spaces." }, 400);
  const { key, requestId, operationId, persistKeychain } = parsed.data;
  if (!matchesStorageOperation(operation, parsed.data)) return respond({ error: "This run has changed. Reload before sending a key." }, 409);
  await expireHandoffs();
  const db = getDb();
  const sameRequest = and(eq(mobileCredentials.userId, user.userId), eq(mobileCredentials.requestId, requestId));
  const existing = (await db.select().from(mobileCredentials).where(sameRequest).limit(1))[0];
  if (existing) {
    if (existing.operationId !== operationId) return respond({ error: "Reload before starting this handoff." }, 409);
    if (existing.status === "pending" && existing.ciphertext && existing.iv) {
      try {
        const original = await openKey(existing.ciphertext, existing.iv, env.MOBILE_CREDENTIAL_ENCRYPTION_KEY,
          { operationId, userId: user.userId, requestId, persistKeychain }, existing.expiresAt);
        if (original !== key) return respond({ error: "This request already carried a different key. Reload to replace it." }, 409);
      } catch { return respond({ error: "This handoff is unavailable. Reload to try again." }, 409); }
    }
    return respond({ item: publicRecord(existing) });
  }
  try {
    const encrypted = await sealKey(key, env.MOBILE_CREDENTIAL_ENCRYPTION_KEY, { operationId, userId: user.userId, requestId, persistKeychain });
    const record = { id: crypto.randomUUID(), operationId, userId: user.userId, requestId,
      ...encrypted, status: "pending" as const, expiresAt: Date.now() + HANDOFF_TTL_MS,
      createdAt: new Date().toISOString() };
    const inserted = await db.insert(mobileCredentials).values(record).onConflictDoNothing().returning();
    if (!inserted[0]) return respond({ error: "A save is already in progress. Reload to check it." }, 409);
    return respond({ item: publicRecord(inserted[0]) }, 201);
  } catch { return respond({ error: "Your key could not be handed off. Try again." }, 503); }
}
