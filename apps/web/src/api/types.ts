export type ProjectSummary = {
  name: string;
  config_path: string;
  config_exists: boolean;
  latest_metrics: Record<string, unknown>;
  latest_job_id: string | null;
  latest_job_status: string | null;
  latest_snapshot_id: string | null;
};

export type ProjectConfigResponse = {
  project: string;
  config_path: string;
  raw_config: Record<string, unknown>;
  effective_config: Record<string, unknown>;
  defaults: Record<string, unknown>;
};

export type JobStep = {
  id: number;
  step_key: string;
  label: string;
  step_order: number;
  status: string;
  exit_code: number | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type JobRun = {
  id: string;
  project: string;
  pipeline: string;
  execution_mode: string;
  status: string;
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  snapshot_id: string | null;
  steps: JobStep[];
};

export type ArtifactFile = {
  name: string;
  url: string;
};

export type ArtifactSummary = {
  metrics_rows: Record<string, unknown>[];
  manifest: Record<string, unknown>;
  report_markdown: string;
  images: ArtifactFile[];
  artifact_files: ArtifactFile[];
  meta_files: ArtifactFile[];
};

export type ProjectDetail = ProjectSummary & {
  latest: {
    metrics_rows: Record<string, unknown>[];
    manifest: Record<string, unknown>;
    report_markdown: string;
    images: string[];
    files: string[];
  };
  recent_runs: {
    job_id: string;
    run_id: string;
    created_at: string;
  }[];
};

export type RunListItem = {
  run_id: string;
  job_id: string;
  pipeline: string;
  status: string;
  created_at: string;
  metrics_rows: Record<string, unknown>[];
  images: ArtifactFile[];
};

export type RunDetail = {
  run_id: string;
  job_id: string;
  project: string;
  pipeline: string;
  status: string;
  created_at: string;
  artifacts_dir: string;
  meta_dir: string;
  config_snapshot_path: string;
  metrics_rows: Record<string, unknown>[];
  manifest: Record<string, unknown>;
  report_markdown: string;
  images: ArtifactFile[];
  artifact_files: ArtifactFile[];
  meta_files: ArtifactFile[];
};

export type IssueDetail = {
  code: string;
  message: string;
  suggestion: string | null;
  detail: Record<string, unknown>;
};

export type DateRange = {
  min: string | null;
  max: string | null;
};

export type WindowCoverage = {
  enabled: boolean;
  reason?: string;
  window_start?: string | null;
  window_end?: string | null;
  expected_code_count?: number;
  raw_codes_with_data?: number;
  clean_codes_with_data?: number;
  raw_missing_code_count?: number;
  clean_missing_code_count?: number;
  raw_rows_in_window?: number;
  clean_rows_in_window?: number;
  raw_window_range?: DateRange;
  clean_window_range?: DateRange;
};

export type NetworkCheck = {
  key: string;
  label: string;
  url: string;
  reachable: boolean;
  http_status: number | null;
  latency_ms: number | null;
  error_code: string | null;
  error_summary: string | null;
  suggestion: string | null;
};

export type NetworkDiagnostics = {
  proxy_url: string | null;
  ca_bundle_path: string | null;
  connect_timeout_seconds: number;
  read_timeout_seconds: number;
  using_proxy: boolean;
  using_custom_ca: boolean;
  ca_bundle_exists: boolean;
  blocking_issues: string[];
  blocking_issue_details: IssueDetail[];
  warnings: string[];
  checks: NetworkCheck[];
};

export type DatabaseStatus = {
  configured_path: string | null;
  resolved_path?: string;
  explicit_configured: boolean;
  path_is_absolute: boolean;
  exists: boolean;
  sqlite_openable: boolean;
  tables: string[];
  raw_table: string;
  clean_table: string;
  raw_rows: number;
  clean_rows: number;
  raw_codes: number;
  clean_codes: number;
  raw_date_range: DateRange;
  clean_date_range: DateRange;
  file_size_bytes: number | null;
  modified_at: string | null;
  window_coverage: WindowCoverage;
  ready: boolean;
  issues: string[];
};

export type PreparationDecisionTrace = {
  stage: string;
  message: string;
  detail: Record<string, unknown>;
};

export type ProjectReadiness = {
  project: string;
  pipeline: string | null;
  ready: boolean;
  config: {
    path: string;
    exists: boolean;
  };
  config_path: string;
  universe_exists: boolean;
  universe_path: string;
  db_status: DatabaseStatus;
  network_status: NetworkDiagnostics;
  preparation: {
    action: string | null;
    decision_key: string | null;
    reason: string | null;
    rebuild_clean_only: boolean;
  };
  decision_trace: PreparationDecisionTrace[];
  required_upstreams: string[];
  blocking_issues: string[];
  warning_details: IssueDetail[];
  blocking_issue_details: IssueDetail[];
  warnings: string[];
};

export type ProjectDoctor = ProjectReadiness;
