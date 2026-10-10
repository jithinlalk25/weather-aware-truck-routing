import type { Heatmap, Place, Plan, PlanRequest } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly fields: Record<string, string[]>;

  constructor(status: number, message: string, fields: Record<string, string[]> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

function flatten(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(flatten);
  if (value && typeof value === "object") return Object.values(value).flatMap(flatten);
  return [];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (res.ok) return (await res.json()) as T;

  let body: Record<string, unknown> = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON error page */
  }
  const fields: Record<string, string[]> = {};
  for (const [key, value] of Object.entries(body)) {
    if (key !== "detail") fields[key] = flatten(value);
  }
  const detail =
    typeof body.detail === "string"
      ? body.detail
      : res.status === 429
        ? "Too many requests. Please wait a moment and try again."
        : Object.values(fields).flat()[0] ?? `Request failed (${res.status}).`;
  throw new ApiError(res.status, detail, fields);
}

export const api = {
  geocode: (q: string, signal?: AbortSignal) =>
    request<{ results: Place[] }>(`/api/geocode?q=${encodeURIComponent(q)}`, { signal }).then(
      (r) => r.results,
    ),
  createPlan: (body: PlanRequest) =>
    request<Plan>("/api/plans", { method: "POST", body: JSON.stringify(body) }),
  getPlan: (id: string) => request<Plan>(`/api/plans/${id}`),
  getHeatmap: (id: string) => request<Heatmap>(`/api/plans/${id}/heatmap`),
};
