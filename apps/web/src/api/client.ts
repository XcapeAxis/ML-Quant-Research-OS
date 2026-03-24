import type {
  ArtifactSummary,
  JobRun,
  NetworkDiagnostics,
  ProjectConfigResponse,
  ProjectDetail,
  ProjectDoctor,
  ProjectReadiness,
  ProjectSummary,
  RunDetail,
  RunListItem,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; mode: string; max_concurrent_jobs: number }>("/api/health"),
  listProjects: () => request<ProjectSummary[]>("/api/projects"),
  getProject: (project: string) => request<ProjectDetail>(`/api/projects/${project}`),
  getProjectConfig: (project: string) => request<ProjectConfigResponse>(`/api/projects/${project}/config`),
  getProjectReadiness: (project: string, pipeline?: string) =>
    request<ProjectReadiness>(
      pipeline
        ? `/api/projects/${project}/readiness?pipeline=${encodeURIComponent(pipeline)}`
        : `/api/projects/${project}/readiness`,
    ),
  getProjectDoctor: (project: string, pipeline?: string) =>
    request<ProjectDoctor>(
      pipeline
        ? `/api/projects/${project}/doctor?pipeline=${encodeURIComponent(pipeline)}`
        : `/api/projects/${project}/doctor`,
    ),
  getNetworkDiagnostics: () => request<NetworkDiagnostics>("/api/platform/network/diagnostics"),
  updateProjectConfig: (project: string, payload: Record<string, unknown>) =>
    request<ProjectConfigResponse>(`/api/projects/${project}/config`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  getLatestArtifacts: (project: string) => request<ArtifactSummary>(`/api/projects/${project}/latest/artifacts`),
  listJobs: (project?: string) => request<JobRun[]>(project ? `/api/jobs?project=${project}` : "/api/jobs"),
  getJob: (jobId: string) => request<JobRun>(`/api/jobs/${jobId}`),
  createJob: (payload: { project: string; pipeline: string; execution_mode: string }) =>
    request<JobRun>("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelJob: (jobId: string) =>
    request<JobRun>(`/api/jobs/${jobId}/cancel`, {
      method: "POST",
    }),
  listRuns: (project: string) => request<RunListItem[]>(`/api/projects/${project}/runs`),
  getRun: (project: string, runId: string) => request<RunDetail>(`/api/projects/${project}/runs/${runId}`),
};
