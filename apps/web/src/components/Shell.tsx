import {
  AppstoreOutlined,
  BarChartOutlined,
  ControlOutlined,
  FundProjectionScreenOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Space, Typography } from "antd";
import { PropsWithChildren } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ProjectPicker } from "./ProjectPicker";

const { Header, Content, Sider } = Layout;

const items = [
  { key: "/projects", icon: <AppstoreOutlined />, label: "项目总览" },
  { key: "/config", icon: <ControlOutlined />, label: "配置中心" },
  { key: "/runs", icon: <PlayCircleOutlined />, label: "运行中心" },
  { key: "/results", icon: <BarChartOutlined />, label: "结果中心" },
  { key: "/runs/_detail", icon: <FundProjectionScreenOutlined />, label: "运行详情" },
];

export function Shell({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigate = useNavigate();
  const selectedKey = location.pathname.startsWith("/runs/") ? "/runs/_detail" : location.pathname;

  return (
    <Layout className="app-shell">
      <Sider width={240} theme="light" className="app-sider">
        <div className="brand-panel">
          <Typography.Text className="brand-eyebrow">BackTest Platform</Typography.Text>
          <Typography.Title level={3} className="brand-title">
            本地回测工作台
          </Typography.Title>
          <Typography.Paragraph className="brand-copy">
            以配置、任务和结果快照为核心，将终端式回测升级为公司内部可用的平台。
          </Typography.Paragraph>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={items}
          onClick={({ key }) => {
            if (key !== "/runs/_detail") {
              navigate(key);
            }
          }}
          className="app-menu"
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space align="center" size="large" className="header-row">
            <div>
              <Typography.Text className="header-eyebrow">内部工具</Typography.Text>
              <Typography.Title level={4} className="header-title">
                量化回测控制台
              </Typography.Title>
            </div>
            <ProjectPicker />
          </Space>
        </Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
