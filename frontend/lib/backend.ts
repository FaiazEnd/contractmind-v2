/**
 * Runtime helper for calling the internal `backend` Vercel service via its injected
 * `BACKEND_URL` service binding (resolved at runtime in server functions only).
 */
export function buildBackendUrl(path: string): URL {
  const base = process.env.BACKEND_URL;
  if (!base) {
    throw new Error('BACKEND_URL service binding is not available in this context');
  }
  return new URL(path, base);
}

export async function fetchBackend(path: string, init?: RequestInit): Promise<Response> {
  return fetch(buildBackendUrl(path), init);
}
