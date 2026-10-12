import { CloudDownloadOutlined } from "@ant-design/icons";
import { Badge, Button, Layout, Menu, message } from "antd";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api/endpoints";
import { TEXT } from "../constants/options";
import { useAsync } from "../hooks/useAsync";

import ModerationDrawer from "./ModerationDrawer";

const NAV_ITEMS = [
  { key: "/", label: "仪表盘" },
  { key: "/politics", label: "政治" },
  { key: "/economy", label: "经济" },
  { key: "/finance", label: "金融" },
  { key: "/military", label: "军事" },
  { key: "/sources", label: "源管理" },
  { key: "/tasks", label: "任务管理" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collecting, setCollecting] = useState(false);

  const pending = useAsync(() => api.moderations(), []);
  const pendingCount = pending.data?.items.length ?? 0;

  async function manualCollect() {
    setCollecting(true);
    try {
      const { items } = await api.tasks();
      const task = items.find((item) => item.kind === "collect" && item.enabled);
      if (!task) {
        message.warning("没有启用的采集任务，请先在任务管理中创建");
        return;
      }
      const result = await api.runTask(task.id);
      if (result.status === "failed") {
        message.error(`「${task.name}」执行失败：${result.errors.join("；") || "未知原因"}`);
      } else {
        message.success(`「${task.name}」已执行：新增 ${result.new} 条`);
      }
      pending.reload();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setCollecting(false);
    }
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Header className="aurora-header">
        <span className="aurora-logo">Aurora</span>
        <Menu
          className="aurora-nav"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
        <div className="aurora-actions">
          <Badge count={pendingCount} size="small">
            <Button onClick={() => setDrawerOpen(true)}>{TEXT.moderation}</Button>
          </Badge>
          <Button
            type="primary"
            icon={<CloudDownloadOutlined />}
            loading={collecting}
            onClick={manualCollect}
          >
            {TEXT.manualCollect}
          </Button>
        </div>
      </Layout.Header>
      <Layout.Content>
        <div className="aurora-content">
          <Outlet />
        </div>
      </Layout.Content>
      <ModerationDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onChanged={pending.reload}
      />
    </Layout>
  );
}
