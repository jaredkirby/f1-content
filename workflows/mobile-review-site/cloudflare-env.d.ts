declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    MOBILE_CREDENTIAL_ENCRYPTION_KEY?: string;
    MOBILE_CREDENTIAL_OPERATOR_TOKEN?: string;
  }
}
