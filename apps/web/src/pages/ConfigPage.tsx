import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  List,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import Editor from "@monaco-editor/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { useProjectContext } from "../App";
import { api } from "../api/client";
import type { IssueDetail, ProjectDoctor, ProjectReadiness } from "../api/types";
import { safeParseJson, setNestedValue } from "../lib/config";
import { formatDateTime, formatFileSize, formatLatency } from "../lib/display";

type FieldConfig = {
  label: string;
  path: string[];
  type: "string" | "number";
};

const fields: FieldConfig[] = [
  { label: "db_path", path: ["db_path"], type: "string" },
  { label: "strategy_mode", path: ["strategy_mode"], type: "string" },
  { label: "freq", path: ["freq"], type: "string" },
  { label: "start_date", path: ["start_date"], type: "string" },
  { label: "end_date", path: ["end_date"], type: "string" },
  { label: "cash", path: ["cash"], type: "number" },
  { label: "commission", path: ["commission"], type: "number" },
  { label: "stamp_duty", path: ["stamp_duty"], type: "number" },
  { label: "slippage", path: ["slippage"], type: "number" },
  { label: "lookback", path: ["lookback"], type: "number" },
  { label: "topk", path: ["topk"], type: "number" },
  { label: "stock_num", path: ["stock_num"], type: "number" },
  { label: "limit_days_window", path: ["limit_days_window"], type: "number" },
  { label: "stoploss_limit", path: ["stoploss_limit"], type: "number" },
  { label: "take_profit_ratio", path: ["take_profit_ratio"], type: "number" },
  { label: "market_stoploss_ratio", path: ["market_stoploss_ratio"], type: "number" },
  { label: "benchmark_code", path: ["baselines", "benchmark_code"], type: "string" },
  { label: "random_trials", path: ["baselines", "random_trials"], type: "number" },
];

const doctorPipeline = "full_analysis_pack";

function readValue(payload: Record<string, unknown>, path: string[]) {
  return path.reduce<unknown>((acc, key) => {
    if (!acc || typeof acc !== "object") {
      return undefined;
    }
    return (acc as Record<string, unknown>)[key];
  }, payload);
}

function formatDateRange(value?: { min: string | null; max: string | null }): string {
  if (!value) {
    return "-";
  }
  if (!value.min && !value.max) {
    return "-";
  }
  return `${value.min ?? "-"} ~ ${value.max ?? "-"}`;
}

function formatWindowCoverage(readiness?: ProjectReadiness | ProjectDoctor): string {
  const coverage = readiness?.db_status.window_coverage;
  if (!coverage) {
    return "-";
  }
  if (!coverage.enabled) {
    if (coverage.reason === "end_date_missing") {
      return "当前配置未设置 end_date，窗口覆盖按增量更新处理。";
    }
    if (coverage.reason === "universe_missing") {
      return "股票池尚未准备完成，暂时无法计算窗口覆盖。";
    }
    if (coverage.reason === "db_unavailable") {
      return "数据库尚未就绪，无法检查窗口覆盖。";
    }
    return "窗口覆盖暂不可用。";
  }
  return [
    `窗口 ${coverage.window_start ?? "-"} ~ ${coverage.window_end ?? "-"}`,
    `raw ${coverage.raw_codes_with_data ?? 0}/${coverage.expected_code_count ?? 0}`,
    `clean ${coverage.clean_codes_with_data ?? 0}/${coverage.expected_code_count ?? 0}`,
  ].join(" | ");
}

function renderIssueDescription(items: IssueDetail[]): ReactNode {
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

function IssueAlert(props: {
  type: "error" | "warning";
  title: string;
  items: IssueDetail[];
}) {
  const { type, title, items } = props;
  if (!items.length) {
    return null;
  }
  return <Alert type={type} showIcon message={title} description={renderIssueDescription(items)} />;
}

export function ConfigPage() {
  const queryClient = useQueryClient();
  const { selectedProject, projects } = useProjectContext();
  const [jsonText, setJsonText] = useState("");
  const [configValue, setConfigValue] = useState<Record<string, unknown>>({});
  const [messageApi, contextHolder] = message.useMessage();

  const currentProject = projects.find((project) => project.name === selectedProject);
  const configQuery = useQuery({
    queryKey: ["project-config", selectedProject],
    queryFn: () => api.getProjectConfig(selectedProject!),
    enabled: Boolean(selectedProject && currentProject?.config_exists),
  });
  const readinessQuery = useQuery({
    queryKey: ["project-readiness", selectedProject, doctorPipeline],
    queryFn: () => api.getProjectReadiness(selectedProject!, doctorPipeline),
    enabled: Boolean(selectedProject && currentProject?.config_exists),
    refetchInterval: 15_000,
  });
  const doctorQuery = useQuery({
    queryKey: ["project-doctor", selectedProject, doctorPipeline],
    queryFn: () => api.getProjectDoctor(selectedProject!, doctorPipeline),
    enabled: Boolean(selectedProject && currentProject?.config_exists),
  });

  useEffect(() => {
    if (!configQuery.data) {
      return;
    }
    setConfigValue(configQuery.data.raw_config);
    setJsonText(JSON.stringify(configQuery.data.raw_config, null, 2));
  }, [configQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateProjectConfig(selectedProject!, payload),
    onSuccess: () => {
      messageApi.success("配置已保存。");
      void queryClient.invalidateQueries({ queryKey: ["project-config", selectedProject] });
      void queryClient.invalidateQueries({ queryKey: ["project-readiness", selectedProject] });
      void queryClient.invalidateQueries({ queryKey: ["project-doctor", selectedProject] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error: Error) => {
      messageApi.error(error.message);
    },
  });

  const readiness = readinessQuery.data;
  const doctor = doctorQuery.data;
  const doctorTrace = useMemo(() => doctor?.decision_trace ?? [], [doctor]);

  if (!selectedProject) {
    return <Card className="panel-card">请先选择项目。</Card>;
  }
  if (!currentProject?.config_exists) {
    return <Card className="panel-card">该项目当前只有结果快照，没有可编辑的配置文件。</Card>;
  }

  return (
    <div className="page-stack">
      {contextHolder}
      <Card className="panel-card">
        <Space align="center" size="middle" wrap>
          <Typography.Title level={4} className="tight-title">
            配置中心
          </Typography.Title>
          <Tag color="cyan">{selectedProject}</Tag>
          <Typography.Text type="secondary">
            常用参数可直接表单编辑，完整 JSON 仍然是真实配置源。
          </Typography.Text>
        </Space>
      </Card>

      <Card
        title="运行前检查"
        className="panel-card"
        extra={
          <Button
            onClick={() => {
              void readinessQuery.refetch();
              void doctorQuery.refetch();
            }}
            loading={readinessQuery.isFetching || doctorQuery.isFetching}
          >
            重新体检
          </Button>
        }
      >
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <Descriptions column={{ xs: 1, xl: 2 }}>
            <Descriptions.Item label="配置文件">{readiness?.config_path ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="股票池文件">
              {readiness?.universe_exists ? <Tag color="success">已存在</Tag> : <Tag color="warning">待构建</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="显式 db_path">
              {doctor?.db_status.configured_path ?? readiness?.db_status.configured_path ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="数据库状态">
              {doctor?.db_status.ready ? <Tag color="success">可用</Tag> : <Tag color="error">不可用</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="预处理决策" span={2}>
              {doctor?.preparation.reason ?? readiness?.preparation.reason ?? "保存配置后将自动刷新。"}
            </Descriptions.Item>
          </Descriptions>

          <IssueAlert type="error" title="当前仍有阻断项" items={doctor?.blocking_issue_details ?? []} />
          <IssueAlert type="warning" title="附加提示" items={doctor?.warning_details ?? []} />
        </Space>
      </Card>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={12}>
          <Card title="数据库与覆盖诊断" className="panel-card">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="解析后路径">{doctor?.db_status.resolved_path ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="文件大小">{formatFileSize(doctor?.db_status.file_size_bytes)}</Descriptions.Item>
              <Descriptions.Item label="最后修改时间">{formatDateTime(doctor?.db_status.modified_at)}</Descriptions.Item>
              <Descriptions.Item label="原始表 / 清洗表">
                {doctor ? `${doctor.db_status.raw_table} / ${doctor.db_status.clean_table}` : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="原始行数 / 清洗行数">
                {doctor ? `${doctor.db_status.raw_rows} / ${doctor.db_status.clean_rows}` : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="原始代码数 / 清洗代码数">
                {doctor ? `${doctor.db_status.raw_codes} / ${doctor.db_status.clean_codes}` : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="原始日期范围">{formatDateRange(doctor?.db_status.raw_date_range)}</Descriptions.Item>
              <Descriptions.Item label="清洗日期范围">{formatDateRange(doctor?.db_status.clean_date_range)}</Descriptions.Item>
              <Descriptions.Item label="窗口覆盖">{formatWindowCoverage(doctor)}</Descriptions.Item>
              <Descriptions.Item label="所需上游">
                {doctor?.required_upstreams.length ? doctor.required_upstreams.join(", ") : "当前无需联网补数"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="预处理决策轨迹" className="panel-card">
            {doctorTrace.length ? (
              <List
                size="small"
                dataSource={doctorTrace}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                      <Space wrap size={[8, 4]}>
                        <Tag color={item.stage === "decision" ? "gold" : "default"}>{item.stage}</Tag>
                        <Typography.Text>{item.message}</Typography.Text>
                      </Space>
                      {Object.keys(item.detail ?? {}).length ? (
                        <Typography.Text type="secondary">
                          {JSON.stringify(item.detail, null, 2)}
                        </Typography.Text>
                      ) : null}
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Typography.Text type="secondary">当前没有可展示的预处理决策轨迹。</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>

      <Card title="网络体检" className="panel-card">
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          dataSource={doctor?.network_status.checks ?? []}
          locale={{ emptyText: "当前没有网络检查结果" }}
          columns={[
            { title: "上游", dataIndex: "label" },
            {
              title: "状态",
              dataIndex: "reachable",
              render: (value: boolean) => (
                <Tag color={value ? "success" : "error"}>{value ? "可达" : "失败"}</Tag>
              ),
            },
            { title: "HTTP", dataIndex: "http_status", render: (value: number | null) => value ?? "-" },
            { title: "延迟", dataIndex: "latency_ms", render: (value: number | null) => formatLatency(value) },
            { title: "错误码", dataIndex: "error_code", render: (value: string | null) => value ?? "-" },
            {
              title: "摘要",
              dataIndex: "error_summary",
              render: (_: string | null, row: ProjectDoctor["network_status"]["checks"][number]) =>
                row.error_summary ?? row.url,
            },
          ]}
        />
      </Card>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={10}>
          <Card title="常用参数" className="panel-card">
            <Form layout="vertical">
              {fields.map((field) => {
                const value = readValue(configValue, field.path);
                return (
                  <Form.Item key={field.label} label={field.label}>
                    {field.type === "number" ? (
                      <InputNumber
                        value={
                          typeof value === "number"
                            ? value
                            : value === undefined || value === null
                              ? undefined
                              : Number(value)
                        }
                        onChange={(next) => {
                          const updated = setNestedValue(configValue, field.path, next);
                          setConfigValue(updated);
                          setJsonText(JSON.stringify(updated, null, 2));
                        }}
                        style={{ width: "100%" }}
                      />
                    ) : field.label === "strategy_mode" ? (
                      <Select
                        value={typeof value === "string" ? value : undefined}
                        onChange={(next) => {
                          const updated = setNestedValue(configValue, field.path, next);
                          setConfigValue(updated);
                          setJsonText(JSON.stringify(updated, null, 2));
                        }}
                        options={[
                          { label: "momentum", value: "momentum" },
                          { label: "limit_up_screening", value: "limit_up_screening" },
                        ]}
                      />
                    ) : (
                      <Input
                        value={typeof value === "string" ? value : value === undefined || value === null ? "" : String(value)}
                        onChange={(event) => {
                          const updated = setNestedValue(configValue, field.path, event.target.value);
                          setConfigValue(updated);
                          setJsonText(JSON.stringify(updated, null, 2));
                        }}
                      />
                    )}
                  </Form.Item>
                );
              })}
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card
            title="完整 JSON"
            className="panel-card"
            extra={
              <Button
                type="primary"
                loading={saveMutation.isPending}
                onClick={() => {
                  try {
                    const parsed = safeParseJson(jsonText);
                    setConfigValue(parsed);
                    saveMutation.mutate(parsed);
                  } catch (error) {
                    messageApi.error(error instanceof Error ? error.message : "JSON 格式无效。");
                  }
                }}
              >
                保存配置
              </Button>
            }
          >
            <Editor
              height="640px"
              defaultLanguage="json"
              value={jsonText}
              onChange={(value) => setJsonText(value ?? "{}")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                scrollBeyondLastLine: false,
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
