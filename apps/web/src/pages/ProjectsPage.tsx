import { useQuery } from "@tanstack/react-query";
import { Card, Col, Empty, Row, Statistic, Table, Tag, Typography } from "antd";
import ReactECharts from "echarts-for-react";

import { api } from "../api/client";
import type { ProjectSummary } from "../api/types";
import { metricNumber } from "../lib/config";
import { statusColor, translatePipeline, translateStatus } from "../lib/display";

function buildChartOptions(projects: ProjectSummary[]) {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 20, top: 20, bottom: 48 },
    xAxis: {
      type: "category",
      data: projects.map((item) => item.name),
      axisLabel: { rotate: 18 },
    },
    yAxis: { type: "value", name: "总收益率" },
    series: [
      {
        type: "bar",
        data: projects.map((item) => metricNumber(item.latest_metrics, "total_return") ?? 0),
        itemStyle: {
          color: "#0f766e",
          borderRadius: [8, 8, 0, 0],
        },
      },
    ],
  };
}

export function ProjectsPage() {
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    refetchInterval: 10_000,
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listJobs(),
    refetchInterval: 5_000,
  });

  const projects = projectsQuery.data ?? [];
  const activeJobs = (jobsQuery.data ?? []).filter((job) => ["queued", "running", "cancelling"].includes(job.status));

  return (
    <div className="page-stack">
      <Row gutter={[20, 20]}>
        <Col xs={24} md={8}>
          <Card className="metric-card">
            <Statistic title="项目总数" value={projects.length} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="metric-card">
            <Statistic title="运行中任务" value={activeJobs.length} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="metric-card">
            <Statistic title="可编辑项目" value={projects.filter((project) => project.config_exists).length} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={14}>
          <Card title="项目收益概览" className="panel-card">
            {projects.length ? (
              <ReactECharts option={buildChartOptions(projects)} style={{ height: 320 }} />
            ) : (
              <Empty description="暂无项目数据" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="当前活跃任务" className="panel-card">
            {activeJobs.length ? (
              <div className="job-list">
                {activeJobs.map((job) => (
                  <div key={job.id} className="job-list-item">
                    <div>
                      <Typography.Text strong>{job.project}</Typography.Text>
                      <Typography.Paragraph type="secondary" className="tight-paragraph">
                        {translatePipeline(job.pipeline)}
                      </Typography.Paragraph>
                    </div>
                    <Tag color={statusColor(job.status)}>{translateStatus(job.status)}</Tag>
                  </div>
                ))}
              </div>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无活跃任务" />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="项目列表" className="panel-card">
        <Table
          rowKey="name"
          dataSource={projects}
          pagination={false}
          columns={[
            {
              title: "项目",
              dataIndex: "name",
              render: (_, row: ProjectSummary) => (
                <div>
                  <Typography.Text strong>{row.name}</Typography.Text>
                  <div>
                    <Tag color={row.config_exists ? "green" : "default"}>
                      {row.config_exists ? "可编辑配置" : "仅查看结果"}
                    </Tag>
                  </div>
                </div>
              ),
            },
            {
              title: "总收益率",
              render: (_, row: ProjectSummary) => {
                const value = metricNumber(row.latest_metrics, "total_return");
                return value === null ? "-" : `${(value * 100).toFixed(1)}%`;
              },
            },
            {
              title: "夏普比率",
              render: (_, row: ProjectSummary) => {
                const value = metricNumber(row.latest_metrics, "sharpe_ratio");
                return value === null ? "-" : value.toFixed(2);
              },
            },
            {
              title: "最近任务",
              render: (_, row: ProjectSummary) =>
                row.latest_job_status ? (
                  <Tag color={statusColor(row.latest_job_status)}>{translateStatus(row.latest_job_status)}</Tag>
                ) : (
                  "-"
                ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
