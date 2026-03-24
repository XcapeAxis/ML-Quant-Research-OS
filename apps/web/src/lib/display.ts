export const statusTextMap: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  succeeded: "已完成",
  failed: "失败",
  cancelling: "取消中",
  cancelled: "已取消",
  skipped: "已跳过",
  pending: "待执行",
};

export const pipelineTextMap: Record<string, string> = {
  data_refresh: "数据准备",
  signal_build: "信号构建",
  backtest_only: "单次回测",
  full_analysis_pack: "完整分析包",
};

export const executionModeTextMap: Record<string, string> = {
  parallel: "并行",
  serial: "串行",
};

export function translateStatus(status: string): string {
  return statusTextMap[status] ?? status;
}

export function translatePipeline(pipeline: string): string {
  return pipelineTextMap[pipeline] ?? pipeline;
}

export function translateExecutionMode(mode: string): string {
  return executionModeTextMap[mode] ?? mode;
}

export function statusColor(status: string): string {
  if (status === "running" || status === "cancelling") {
    return "processing";
  }
  if (status === "failed") {
    return "error";
  }
  if (status === "succeeded") {
    return "success";
  }
  if (status === "queued") {
    return "gold";
  }
  return "default";
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
    hour12: false,
  }).format(new Date(value));
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) {
    return "-";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatLatency(latencyMs: number | null | undefined): string {
  if (latencyMs === null || latencyMs === undefined || Number.isNaN(latencyMs)) {
    return "-";
  }
  return `${latencyMs.toFixed(0)} ms`;
}
