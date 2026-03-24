import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Radio, Select, Space, Table, Tag, Typography, message } from "antd";
import { Link } from "react-router-dom";

import { useProjectContext } from "../App";
import { api } from "../api/client";
import type { IssueDetail } from "../api/types";
import { formatDateTime, statusColor, translateExecutionMode, translatePipeline, translateStatus } from "../lib/display";

const pipelineOptions = [
  { label: "数据准备", value: "data_refresh" },
  { label: "信号构建", value: "signal_build" },
  { label: "单次回测", value: "backtest_only" },
  { label: "完整分析包", value: "full_analysis_pack" },
];

function renderIssueDescription(items: IssueDetail[]) {
  return (
    <Space direction="vertical" size="small" style={{ width: "100%" }}>
      {items.map((item) => (
        <div key={`${item.code}-${item.message}`}>
          <Space wrap size={[8, 4]}>
            <Tag>{item.code}</Tag>
            <Typography.Text>{item.message}</Typography.Text>
          </Space>
          {item.suggestion ? (
            <div>
              <Typography.Text type="secondary">{item.suggestion}</Typography.Text>
            </div>
          ) : null}
        </div>
      ))}
    </Space>
  );
}

export function RunsPage() {
  const queryClient = useQueryClient();
  const { selectedProject, projects } = useProjectContext();
  const [messageApi, contextHolder] = message.useMessage();
  const currentProject = projects.find((project) => project.name === selectedProject);
  const [pipeline, setPipeline] = React.useState("backtest_only");
  const [executionMode, setExecutionMode] = React.useState("parallel");

  const jobsQuery = useQuery({
    queryKey: ["jobs", selectedProject],
    queryFn: () => api.listJobs(selectedProject ?? undefined),
    enabled: Boolean(selectedProject),
    refetchInterval: 3_000,
  });
  const readinessQuery = useQuery({
    queryKey: ["project-readiness", selectedProject, pipeline],
    queryFn: () => api.getProjectReadiness(selectedProject!, pipeline),
    enabled: Boolean(selectedProject && currentProject?.config_exists),
    refetchInterval: 15_000,
  });

  const createMutation = useMutation({
    mutationFn: () => api.createJob({ project: selectedProject!, pipeline, execution_mode: executionMode }),
    onSuccess: (job) => {
      messageApi.success(`任务已提交：${job.id}`);
      void queryClient.invalidateQueries({ queryKey: ["jobs", selectedProject] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error: Error) => {
      messageApi.error(error.message);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: () => {
      messageApi.success("已提交取消请求。");
      void queryClient.invalidateQueries({ queryKey: ["jobs", selectedProject] });
    },
    onError: (error: Error) => {
      messageApi.error(error.message);
    },
  });

  if (!selectedProject) {
    return <Card className="panel-card">请先选择项目。</Card>;
  }

  const readiness = readinessQuery.data;
  const blockingIssues = readiness?.blocking_issue_details ?? [];
  const warningIssues = readiness?.warning_details ?? [];

  return (
    <div className="page-stack">
      {contextHolder}
      <Card className="panel-card">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div>
            <Typography.Title level={4} className="tight-title">
              运行中心
            </Typography.Title>
            <Typography.Paragraph type="secondary" className="tight-paragraph">
              通过统一入口提交预置流水线，平台会负责排队、并发控制、日志收集和结果快照。
            </Typography.Paragraph>
          </div>
          <Space wrap size="middle">
            <Select value={pipeline} options={pipelineOptions} onChange={setPipeline} style={{ width: 220 }} placeholder="选择执行流" />
            <Radio.Group
              value={executionMode}
              optionType="button"
              onChange={(event) => setExecutionMode(event.target.value)}
              options={[
                { label: "并行", value: "parallel" },
                { label: "串行", value: "serial" },
              ]}
            />
            <Button
              type="primary"
              onClick={() => createMutation.mutate()}
              loading={createMutation.isPending}
              disabled={!currentProject?.config_exists || blockingIssues.length > 0}
            >
              提交任务
            </Button>
            {!currentProject?.config_exists ? <Tag>该项目仅提供结果查看</Tag> : null}
          </Space>
          {readiness?.preparation.reason ? (
            <Typography.Text type="secondary">预计预处理动作：{readiness.preparation.reason}</Typography.Text>
          ) : null}
        </Space>
      </Card>

      {blockingIssues.length ? (
        <Alert
          type="error"
          showIcon
          message="当前项目未通过提交前检查"
          description={renderIssueDescription(blockingIssues)}
        />
      ) : (
        <Alert type="success" showIcon message="当前执行流已通过提交前检查。" />
      )}

      {warningIssues.length ? (
        <Alert type="warning" showIcon message="附加提示" description={renderIssueDescription(warningIssues)} />
      ) : null}

      <Card title="任务队列" className="panel-card">
        {jobsQuery.data?.length ? (
          <Table
            rowKey="id"
            dataSource={jobsQuery.data}
            pagination={false}
            columns={[
              {
                title: "任务",
                dataIndex: "id",
                render: (value: string) => <Typography.Text code>{value.slice(0, 8)}</Typography.Text>,
              },
              { title: "执行流", dataIndex: "pipeline", render: (value: string) => translatePipeline(value) },
              {
                title: "状态",
                dataIndex: "status",
                render: (value: string) => <Tag color={statusColor(value)}>{translateStatus(value)}</Tag>,
              },
              { title: "模式", dataIndex: "execution_mode", render: (value: string) => translateExecutionMode(value) },
              { title: "创建时间", dataIndex: "created_at", render: (value: string | null) => formatDateTime(value) },
              {
                title: "操作",
                render: (_, row) => (
                  <Space>
                    <Link to={`/runs/${row.id}`}>查看详情</Link>
                    {["queued", "running"].includes(row.status) ? (
                      <Button size="small" danger onClick={() => cancelMutation.mutate(row.id)} loading={cancelMutation.isPending}>
                        取消
                      </Button>
                    ) : null}
                  </Space>
                ),
              },
            ]}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />
        )}
      </Card>
    </div>
  );
}
