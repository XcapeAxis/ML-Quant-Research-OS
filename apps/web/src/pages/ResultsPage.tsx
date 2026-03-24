import { useQueries, useQuery } from "@tanstack/react-query";
import { Card, Col, Empty, Row, Select, Space, Statistic, Table, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import ReactMarkdown from "react-markdown";
import { useMemo, useState } from "react";

import { useProjectContext } from "../App";
import { api } from "../api/client";
import type { RunDetail } from "../api/types";
import { metricNumber } from "../lib/config";
import { translatePipeline } from "../lib/display";

function buildCompareOption(series: { name: string; value: number }[]) {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 20, top: 20, bottom: 48 },
    xAxis: { type: "category", data: series.map((item) => item.name), axisLabel: { rotate: 18 } },
    yAxis: { type: "value", name: "年化收益率" },
    series: [
      {
        type: "bar",
        data: series.map((item) => item.value),
        itemStyle: { color: "#b45309", borderRadius: [8, 8, 0, 0] },
      },
    ],
  };
}

export function ResultsPage() {
  const { selectedProject } = useProjectContext();
  const [selectedRuns, setSelectedRuns] = useState<string[]>([]);

  const latestQuery = useQuery({
    queryKey: ["latest-artifacts", selectedProject],
    queryFn: () => api.getLatestArtifacts(selectedProject!),
    enabled: Boolean(selectedProject),
  });

  const runsQuery = useQuery({
    queryKey: ["runs", selectedProject],
    queryFn: () => api.listRuns(selectedProject!),
    enabled: Boolean(selectedProject),
  });

  const selectedRunQueries = useQueries({
    queries: (selectedRuns.slice(0, 2) ?? []).map((runId) => ({
      queryKey: ["run", selectedProject, runId],
      queryFn: () => api.getRun(selectedProject!, runId),
      enabled: Boolean(selectedProject && runId),
    })),
  });

  const activeDetails = selectedRunQueries.map((query) => query.data).filter((detail): detail is RunDetail => Boolean(detail));
  const primary = activeDetails[0] ?? latestQuery.data;
  const primaryMetrics = primary?.metrics_rows?.[0];

  const compareSeries = useMemo(() => {
    if (activeDetails.length) {
      return activeDetails.map((detail) => ({
        name: detail.run_id.slice(0, 8),
        value: metricNumber(detail.metrics_rows[0], "annualized_return") ?? 0,
      }));
    }
    return (runsQuery.data ?? []).slice(0, 5).map((run) => ({
      name: run.run_id.slice(0, 8),
      value: metricNumber(run.metrics_rows[0], "annualized_return") ?? 0,
    }));
  }, [activeDetails, runsQuery.data]);

  if (!selectedProject) {
    return <Card className="panel-card">请先选择项目。</Card>;
  }

  return (
    <div className="page-stack">
      <Card
        className="panel-card"
        title="结果中心"
        extra={
          <Space>
            <Typography.Text type="secondary">运行对比</Typography.Text>
            <Select
              mode="multiple"
              maxCount={2}
              allowClear
              placeholder="选择 1 到 2 个历史运行"
              value={selectedRuns}
              onChange={setSelectedRuns}
              style={{ minWidth: 320 }}
              options={(runsQuery.data ?? []).map((run) => ({
                label: `${run.run_id.slice(0, 8)} | ${translatePipeline(run.pipeline)}`,
                value: run.run_id,
              }))}
            />
          </Space>
        }
      >
        <Row gutter={[20, 20]}>
          <Col xs={24} md={8}>
            <Card className="metric-card">
              <Statistic title="总收益率" value={metricNumber(primaryMetrics, "total_return") ?? 0} precision={4} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card className="metric-card">
              <Statistic title="夏普比率" value={metricNumber(primaryMetrics, "sharpe_ratio") ?? 0} precision={2} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card className="metric-card">
              <Statistic title="最大回撤" value={metricNumber(primaryMetrics, "max_drawdown") ?? 0} precision={4} />
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={12}>
          <Card title="收益对比" className="panel-card">
            {compareSeries.length ? (
              <ReactECharts option={buildCompareOption(compareSeries)} style={{ height: 320 }} />
            ) : (
              <Empty description="暂无可对比的运行结果" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="指标表" className="panel-card">
            <Table
              rowKey={(row) => Object.entries(row).map(([key, value]) => `${key}:${value}`).join("|")}
              dataSource={activeDetails.length ? activeDetails.flatMap((detail) => detail.metrics_rows) : latestQuery.data?.metrics_rows ?? []}
              pagination={false}
              scroll={{ x: true }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="图表产物" className="panel-card">
        {primary?.images?.length ? (
          <div className="image-grid">
            {primary.images.map((image) => (
              <figure key={image.url} className="image-card">
                <img src={image.url} alt={image.name} />
                <figcaption>{image.name}</figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无图表产物" />
        )}
      </Card>

      <Card title="报告预览" className="panel-card">
        {primary?.report_markdown ? (
          <div className="markdown-panel">
            <ReactMarkdown>{primary.report_markdown}</ReactMarkdown>
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无报告" />
        )}
      </Card>
    </div>
  );
}
