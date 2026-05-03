import axios from "axios";

export const api = axios.create({ baseURL: "/api" });

export type Tag = {
  id: number;
  name: string;
  description?: string | null;
  paper_count?: number;
};

export type Figure = {
  id: number;
  idx: number;
  path: string;
  caption?: string | null;
};

export type PaperListItem = {
  id: number;
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  abstract_zh: string | null;
  categories: string[];
  abs_url: string;
  pdf_url: string;
  published_at: string;
  status: "new" | "to_read" | "not_interested" | "read";
  tags: Tag[];
};

export type PaperDetail = PaperListItem & {
  summary_md: string | null;
  insights_md: string | null;
  followup_md: string | null;
  figures: Figure[];
};

export type PaperNeighbors = {
  previous: PaperListItem | null;
  next: PaperListItem | null;
};

export type Subscription = {
  id: number;
  kind: "category" | "keyword";
  value: string;
  enabled: boolean;
  created_at: string;
  last_fetched_at: string | null;
};

export type Job = {
  id: number;
  paper_id: number | null;
  kind: string;
  status: "pending" | "running" | "done" | "failed";
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type FetchSettings = {
  fetch_lookback_days: number;
  default_fetch_lookback_days: number;
  auto_fetch_enabled: boolean;
  default_auto_fetch_enabled: boolean;
  fetch_time: string;
  default_fetch_time: string;
  server_time: string;
  server_timezone: string;
  server_utc_offset_minutes: number;
  heavy_processing_trigger: HeavyProcessingTrigger;
  default_heavy_processing_trigger: HeavyProcessingTrigger;
};

export type HeavyProcessingTrigger = "on_fetch" | "on_to_read";

export const PaperApi = {
  list: (params: { status?: string; tag?: string; q?: string; page?: number }) =>
    api.get<PaperListItem[]>("/papers", { params }).then((r) => r.data),
  get: (id: number) => api.get<PaperDetail>(`/papers/${id}`).then((r) => r.data),
  neighbors: (id: number, params?: { status?: string; tag?: string }) =>
    api
      .get<PaperNeighbors>(`/papers/${id}/neighbors`, { params })
      .then((r) => r.data),
  patch: (id: number, body: { status?: string; tag_ids?: number[] }) =>
    api.patch<PaperDetail>(`/papers/${id}`, body).then((r) => r.data),
  clearAll: () => api.delete<{ deleted: number }>("/papers").then((r) => r.data),
  reprocess: (id: number, stage: "translate" | "tag" | "summary" | "figures") =>
    api.post(`/papers/${id}/reprocess`, null, { params: { stage } }).then((r) => r.data),
  counts: () => api.get<Record<string, number>>("/papers/stats/counts").then((r) => r.data),
};

export const SubsApi = {
  list: () => api.get<Subscription[]>("/subscriptions").then((r) => r.data),
  create: (body: { kind: string; value: string; enabled?: boolean }) =>
    api.post<Subscription>("/subscriptions", body).then((r) => r.data),
  update: (id: number, body: { kind: string; value: string; enabled: boolean }) =>
    api.patch<Subscription>(`/subscriptions/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/subscriptions/${id}`).then((r) => r.data),
};

export const TagApi = {
  list: (params?: { status?: string }) =>
    api.get<Tag[]>("/tags", { params }).then((r) => r.data),
  create: (body: { name: string; description?: string }) =>
    api.post<Tag>("/tags", body).then((r) => r.data),
  update: (id: number, body: { name?: string; description?: string }) =>
    api.patch<Tag>(`/tags/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/tags/${id}`).then((r) => r.data),
};

export const JobApi = {
  list: () => api.get<Job[]>("/jobs").then((r) => r.data),
  fetchNow: () =>
    api
      .post<{ queued: number; new_papers: number }>("/jobs/fetch")
      .then((r) => r.data),
};

export const SettingsApi = {
  getFetch: () => api.get<FetchSettings>("/settings/fetch").then((r) => r.data),
  updateFetch: (body: {
    fetch_lookback_days?: number;
    auto_fetch_enabled?: boolean;
    fetch_time?: string;
    heavy_processing_trigger?: HeavyProcessingTrigger;
  }) =>
    api.patch<FetchSettings>("/settings/fetch", body).then((r) => r.data),
};
