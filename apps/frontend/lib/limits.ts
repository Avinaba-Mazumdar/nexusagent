/** Keep in sync with MAX_FILE_BYTES in apps/backend/app/routes/documents.py. */
export const MAX_UPLOAD_MB = 1;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

/** Keep in sync with AgentStreamRequestWire.query max_length in apps/backend/app/routes/agent.py. */
export const MAX_QUERY_CHARS = 2000;
/** The character counter appears once the prompt is this long. */
export const QUERY_COUNTER_FROM = 1600;
