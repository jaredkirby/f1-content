import { env } from "cloudflare:workers";
import { and, desc, eq, lte } from "drizzle-orm";
import { getDb } from "@/db";
import { mobileCredentials } from "@/db/schema";
import { matchesOperatorToken, openKey } from "@/lib/credential-box";
import { matchesStorageOperation } from "@/lib/credential-operation.mjs";
import operation from "@/app/data/credential-operation.json";

export const dynamic = "force-dynamic";
const respond = (data: unknown, status = 200) => Response.json(data, { status,
  headers: { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } });
export async function POST(request: Request) {
  // A dedicated operation token is required in addition to Sites' private dispatch.
  const supplied = request.headers.get("authorization")?.replace(/^Bearer /, "") ?? null;
  if (!matchesOperatorToken(supplied, env.MOBILE_CREDENTIAL_OPERATOR_TOKEN || ""))
    return respond({ error: "Operator authorization required." }, 401);
  if (!operation.enabled || !env.MOBILE_CREDENTIAL_ENCRYPTION_KEY)
    return respond({ error: "Credential handoff unavailable." }, 503);
  if (!matchesStorageOperation(operation, {operationId: operation.id, persistKeychain: operation.persistKeychain}))
    return respond({ error: "The storage choice changed. Prepare a fresh handoff." }, 409);
  const db = getDb();
  await db.update(mobileCredentials).set({ status: "expired", ciphertext: null, iv: null })
    .where(and(eq(mobileCredentials.status, "pending"), lte(mobileCredentials.expiresAt, Date.now())));
  const row = (await db.select().from(mobileCredentials)
    .where(and(eq(mobileCredentials.operationId, operation.id), eq(mobileCredentials.status, "pending")))
    .orderBy(desc(mobileCredentials.createdAt)).limit(1))[0];
  if (!row || !row.ciphertext || !row.iv) return respond({ status: "awaiting_key" }, 202);
  try {
    const key = await openKey(row.ciphertext, row.iv, env.MOBILE_CREDENTIAL_ENCRYPTION_KEY,
      { operationId: row.operationId, userId: row.userId, requestId: row.requestId, persistKeychain: operation.persistKeychain }, row.expiresAt);
    // Compare-and-set: two consumers cannot receive the same key.
    const claimed = await db.update(mobileCredentials).set({ status: "consumed", ciphertext: null,
      iv: null, consumedAt: new Date().toISOString() })
      .where(and(eq(mobileCredentials.id, row.id), eq(mobileCredentials.status, "pending")))
      .returning({ id: mobileCredentials.id });
    if (!claimed[0]) return respond({ status: "already_collected" }, 409);
    return respond({ status: "collected", key, operationId: operation.id,
      requestSha256: operation.requestSha256, budgetUsd: operation.budgetUsd, maxCalls: 'maxCalls' in operation ? operation.maxCalls : 1,
      persistKeychain: operation.persistKeychain, handoffId: row.id });
  } catch { return respond({ error: "Credential handoff could not be opened." }, 409); }
}
