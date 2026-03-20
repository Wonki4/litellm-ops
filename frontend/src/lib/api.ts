export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const proxyPath = path.replace(/^\/api\//, "/api/proxy/");

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const res = await fetch(proxyPath, { ...options, headers });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.replace(`/api/proxy/auth/login?return_to=${returnTo}`);
    }
    throw new AuthError("Session expired. Please log in again.");
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API Error ${res.status}`);
  }
  return res.json();
}
