import { Select, Space, Tag, Typography } from "antd";

import { useProjectContext } from "../App";

export function ProjectPicker() {
  const { projects, selectedProject, setSelectedProject } = useProjectContext();

  return (
    <Space size="middle">
      <Typography.Text className="toolbar-label">项目</Typography.Text>
      <Select
        value={selectedProject ?? undefined}
        options={projects.map((project) => ({
          label: project.name,
          value: project.name,
        }))}
        onChange={setSelectedProject}
        style={{ minWidth: 220 }}
        placeholder="选择项目"
      />
      {selectedProject ? (
        <Tag color="geekblue">
          {projects.find((item) => item.name === selectedProject)?.config_exists ? "可编辑配置" : "仅查看结果"}
        </Tag>
      ) : null}
    </Space>
  );
}
