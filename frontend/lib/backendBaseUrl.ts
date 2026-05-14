/**
 * FastAPI base URL (no trailing slash). Used by App Router API proxies.
 *
 * Priority (deployment.md / Vercel):
 * - `BACKEND_URL` — preferred on Vercel (server-only; not exposed to the browser)
 * - `NEXT_PUBLIC_API_URL` — public alias from deployment guide
 * - `NEXT_PUBLIC_BACKEND_URL` — legacy name
 */
export function getBackendBaseUrl(): string {
  const raw =
    process.env.BACKEND_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim() ||
    "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}
