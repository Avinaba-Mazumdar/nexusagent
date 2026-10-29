/** Public hostname of this deployment; override with NEXT_PUBLIC_SITE_HOST for other domains. */
export const SITE_HOST = process.env.NEXT_PUBLIC_SITE_HOST || 'nexusagent.avinaba.com';
/** Days tool audit rows are kept before the scheduled job deletes them (scripts/prune_guests.py). */
export const AUDIT_RETENTION_DAYS = 30;
