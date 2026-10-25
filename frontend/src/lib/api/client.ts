// Small fetch wrapper: every failure becomes an ApiError with a message that
// is safe and understandable to show a recruiter.

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const GENERIC: Record<number, string> = {
  404: "That item no longer exists. It may have been deleted.",
  429: "You're doing that too often. Please wait a moment and try again.",
  500: "Something went wrong on our side. Please try again.",
  502: "The server is temporarily unreachable. Please try again shortly.",
  503: "The server is temporarily unavailable. Please try again shortly.",
  504: "The server took too long to respond. Please try again.",
};

type ErrorBody = { error?: { code?: string; message?: string; fields?: Record<string, string> } };

export async function apiFetch<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...rest,
      headers: {
        Accept: "application/json",
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0, "network_error");
  }

  if (response.status === 204) return undefined as T;

  let data: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null; // e.g. an HTML error page from a proxy
    }
  }

  if (!response.ok) {
    const error = (data as ErrorBody | null)?.error;
    // A non-JSON 5xx comes from the proxy, not Django: the API itself is unreachable.
    const fallback = response.status >= 500 && !error ? GENERIC[502] : GENERIC[response.status];
    throw new ApiError(
      error?.message ?? fallback ?? "Something went wrong. Please try again.",
      response.status,
      error?.code ?? `http_${response.status}`,
      error?.fields ?? {},
    );
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}
