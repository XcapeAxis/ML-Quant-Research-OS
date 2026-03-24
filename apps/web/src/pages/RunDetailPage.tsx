import { useQuery } from "@tanstack/react-query";
import { Button, Card, Descriptions, Empty, Space, Steps, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { formatDateTime, statusColor, translateExecutionMode, translatePipeline, translateStatus } from "../lib/display";

const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);

export function RunDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [logLines, setLogLines] = useState<string[]>([]);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (terminalStatuses.has(query.state.data?.status ?? "") ? false : 2_000),
  });

  useEffect(() => {
    if (!jobId) {
      return;
    }
    setLogLines([]);
    const source = new EventSource(`/api/jobs/${jobId}/events`);
    source.addEventListener("log", (event) => {
      const payload = JSON.parse(event.data) as { line: string };
      setLogLines((prev) => [...prev.slice(-399), payload.line]);
    });
    source.addEventListener("complete", () => {
      source.close();
    });
    source.addEventListener("error", () => {
      source.close();
    });
    return () => source.close();
  }, [jobId]);

  const currentStep = useMemo(() => {
    const running = jobQuery.data?.steps.find((step) => step.status === "running");
    return running?.step_order ?? 0;
  }, [jobQuery.data?.steps]);

  if (!jobId) {
    return <Card className="panel-card">缺少任务 ID。</Card>;
  }

  if (!jobQuery.data) {
    return <Card className="panel-card">正在加载任务详情...</Card>;
  }

  const job = jobQuery.data;

  return (
    <div className="page-stack">
      <Card
        className="panel-card"
        title={`运行详情 | ${job.id.slice(0, 8)}`}
        extra={
          <Space>
            {job.snapshot_id ? <Button onClick={() => navigate("/results")}>打开结果中心</Button> : null}
            <Tag color={statusColor(job.status)}>{translateStatus(job.status)}</Tag>
          </Space>
        }
      >
        <Descriptions column={{ xs: 1, lg: 2 }}>
          <Descriptions.Item label="项目">{job.project}</Descriptions.Item>
          <Descriptions.Item label="执行流">{translatePipeline(job.pipeline)}</Descriptions.Item>
          <Descriptions.Item label="模式">{translateExecutionMode(job.execution_mode)}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDateTime(job.created_at)}</Descriptions.Item>
          <Descriptions.Item label="开始时间">{formatDateTime(job.started_at)}</Descriptions.Item>
          <Descriptions.Item label="结束时间">{formatDateTime(job.finished_at)}</Descriptions.Item>
          <Descriptions.Item label="错误信息" span={2}>
            {job.error_message ?? "-"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="步骤状态" className="panel-card">
        {job.steps.length ? (
          <Steps
            current={currentStep}
            direction="vertical"
            items={job.steps.map((step) => ({
              title: step.label,
              description: `${translateStatus(step.status)}${step.exit_code !== null ? ` | 退出码 ${step.exit_code}` : ""}${step.error_message ? ` | ${step.error_message}` : ""}`,
              status:
                step.status === "succeeded"
                  ? "finish"
                  : step.status === "failed"
                    ? "error"
                    : step.status === "running"
                      ? "process"
                      : "wait",
            }))}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无步骤数据" />
        )}
      </Card>

      <Card title="实时日志" className="panel-card">
        <div className="log-panel">
          {logLines.length ? (
            logLines.map((line, index) => (
              <Typography.Text key={`${index}-${line}`} className="log-line">
                {line}
              </Typography.Text>
            ))
          ) : (
            <Typography.Text type="secondary">等待日志输出...</Typography.Text>
          )}
        </div>
      </Card>
    </div>
  );
}
