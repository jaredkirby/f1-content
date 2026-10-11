import { sqliteTable, text, real, integer, uniqueIndex, index } from "drizzle-orm/sqlite-core";

export const reviewFeedback = sqliteTable("review_feedback", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  requestId: text("request_id").notNull(),
  kind: text("kind", { enum: ["annotation", "decision"] }).notNull(),
  outcome: text("outcome", { enum: ["approved", "rejected"] }),
  comment: text("comment").notNull(),
  timeSec: real("time_sec"),
  eventId: text("event_id").notNull(),
  manifestSha256: text("manifest_sha256").notNull(),
  videoSha256: text("video_sha256").notNull(),
  videoVersion: text("video_version").notNull(),
  modelReceipts: text("model_receipts").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [
  uniqueIndex("feedback_request").on(table.userId, table.requestId),
  index("feedback_review").on(table.userId, table.manifestSha256, table.createdAt),
]);

export const mobileCredentials = sqliteTable("mobile_credentials", {
  id: text("id").primaryKey(),
  operationId: text("operation_id").notNull(),
  userId: text("user_id").notNull(),
  requestId: text("request_id").notNull(),
  ciphertext: text("ciphertext"),
  iv: text("iv"),
  status: text("status", { enum: ["pending", "consumed", "expired"] }).notNull(),
  expiresAt: integer("expires_at").notNull(),
  createdAt: text("created_at").notNull(),
  consumedAt: text("consumed_at"),
}, (table) => [
  uniqueIndex("mobile_credential_request").on(table.userId, table.requestId),
  index("mobile_credential_operation").on(table.operationId, table.status, table.createdAt),
]);
