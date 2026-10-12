import {
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import { useState } from "react";

import { api } from "../api/endpoints";
import type { RunLogItem, TaskInput, TaskItem } from "../api/types";
import PageHeader from "../components/PageHeader";
import { CATEGORY_OPTIONS, CATEGORY_MAP } from "../constants/categories";
import { LOG_STATUS, TASK_KIND_LABELS } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../utils/format";

const EMPTY_TASK: TaskInput = {
  name: "",
  kind: "collect",
  category: null,
  cron: "0 */4 * * *",
  enabled: true,
};

export default function TasksPage() {
  const tasks = useAsync(() => api.tasks(), []);
  const logs = useAsync(() => api.logs(50), []);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [logTask, setLogTask] = useState<TaskItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<TaskItem | null>(null);
  const [form] = Form.useForm<TaskInput>();

  const items = tasks.data?.items ?? [];
  const logItems = logs.data?.items ?? [];

  async function run(task: TaskItem) {
    setRunningId(task.id);
    try {
      const result = await api.runTask(task.id);
      if (result.status === "failed") {
        message.error(`执行失败：${result.errors.join("；") || "未知原因"}`);
      } else {
        message.success(
          `执行完成：抓取 ${result.fetched} 条 / 新增 ${result.new} 条（${result.status}）`,
        );
      }
      tasks.reload();
      logs.reload();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setRunningId(null);
    }
  }

  function openCreate() {
    setEditing(null);
    form.setFieldsValue(EMPTY_TASK);
    setDrawerOpen(true);
  }

  function openEdit(task: TaskItem) {
    setEditing(task);
    form.setFieldsValue({
      name: task.name,
      kind: task.kind,
      category: task.category,
      cron: task.cron,
      enabled: task.enabled,
    });
    setDrawerOpen(true);
  }

  async function submit() {
    const values = await form.validateFields();
    try {
      if (editing) {
        await api.updateTask(editing.id, values);
      } else {
        await api.createTask(values);
      }
      message.success("已保存");
      setDrawerOpen(false);
      tasks.reload();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  const logColumns = [
    { title: "时间", dataIndex: "started_at", key: "started_at", render: formatDateTime },
    { title: "任务", dataIndex: "task_name", key: "task_name" },
    {
      title: "状态",
      key: "status",
      render: (_: unknown, row: RunLogItem) => {
        const status = LOG_STATUS[row.status] ?? { text: row.status, color: "default" };
        return <Tag color={status.color}>{status.text}</Tag>;
      },
    },
    {
      title: "新增 / 抓取",
      key: "counts",
      render: (_: unknown, row: RunLogItem) => `${row.new_count} / ${row.fetched_count}`,
    },
    {
      title: "错误详情",
      key: "error",
      render: (_: unknown, row: RunLogItem) =>
        row.error ? (
          <Tooltip title={row.error}>
            <span className="aurora-muted">{row.error.slice(0, 40)}…</span>
          </Tooltip>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <div className="aurora-stack">
      <PageHeader
        title="定时任务管理"
        tagline="采集与分析任务排期，支持手动立即执行"
        extra={
          <Button type="primary" onClick={openCreate}>
            + 新增任务
          </Button>
        }
      />

      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {items.map((task) => (
          <Card key={task.id} size="small" variant="outlined">
            <Space style={{ width: "100%", justifyContent: "space-between" }} align="start">
              <Space direction="vertical" size={4}>
                <Space size={8} wrap>
                  <strong>{task.name}</strong>
                  <Tag color={task.kind === "collect" ? "blue" : "purple"}>
                    {TASK_KIND_LABELS[task.kind] ?? task.kind}
                  </Tag>
                  <Tag>
                    {task.category
                      ? CATEGORY_MAP[task.category as keyof typeof CATEGORY_MAP]?.label ?? task.category
                      : "全板块"}
                  </Tag>
                  <span className="aurora-muted">cron: {task.cron}</span>
                </Space>
                <span className="aurora-muted">
                  上次 {formatDateTime(task.last_run_at)} · 下次 {formatDateTime(task.next_run_at)}
                </span>
              </Space>
              <Space size={6}>
                <Switch
                  size="small"
                  checked={task.enabled}
                  onChange={async (checked) => {
                    await api.updateTask(task.id, { enabled: checked });
                    tasks.reload();
                  }}
                />
                <Button
                  size="small"
                  type="primary"
                  loading={runningId === task.id}
                  onClick={() => run(task)}
                >
                  立即执行
                </Button>
                <Button size="small" onClick={() => setLogTask(task)}>
                  日志
                </Button>
                <Button size="small" onClick={() => openEdit(task)}>
                  编辑
                </Button>
                <Popconfirm
                  title="删除该任务？"
                  onConfirm={async () => {
                    await api.deleteTask(task.id);
                    message.success("已删除");
                    tasks.reload();
                  }}
                >
                  <Button size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            </Space>
          </Card>
        ))}
      </Space>

      <Card size="small" title="最近运行日志" loading={logs.loading} variant="outlined">
        <Table size="small" rowKey="id" dataSource={logItems} columns={logColumns} />
      </Card>

      <Drawer
        title={logTask ? `${logTask.name} 运行日志` : "运行日志"}
        width={560}
        open={logTask !== null}
        onClose={() => setLogTask(null)}
      >
        <Table
          size="small"
          rowKey="id"
          dataSource={logItems.filter((log) => log.task_id === logTask?.id)}
          columns={logColumns}
        />
      </Drawer>

      <Drawer
        title={editing ? `编辑：${editing.name}` : "新增任务"}
        width={420}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Space>
            <Button onClick={() => setDrawerOpen(false)}>取消</Button>
            <Button type="primary" onClick={submit}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical" initialValues={EMPTY_TASK}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 采集 · 全板块" />
          </Form.Item>
          <Form.Item name="kind" label="类型" rules={[{ required: true }]}>
            <Select
              options={[
                { label: "采集", value: "collect" },
                { label: "分析", value: "analyze" },
              ]}
            />
          </Form.Item>
          <Form.Item name="category" label="板块（留空为全板块）">
            <Select allowClear placeholder="全板块" options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item name="cron" label="cron 表达式" rules={[{ required: true }]}>
            <Input placeholder="0 */4 * * *" />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
