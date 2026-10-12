import {
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import type { SourceInput, SourceItem } from "../api/types";
import PageHeader from "../components/PageHeader";
import { CATEGORY_OPTIONS, CATEGORY_MAP } from "../constants/categories";
import { FEED_TYPES, HEALTH_LABELS, LANGS } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, healthLevel } from "../utils/format";

interface Filters {
  category?: string;
  status?: string;
  keyword?: string;
}

const EMPTY_FORM: SourceInput = {
  name: "",
  url: "",
  feed_type: "rss",
  lang: "en",
  enabled: true,
  categories: [],
};

export default function SourcesPage() {
  const { data, loading, reload } = useAsync(() => api.sources(), []);
  const [filters, setFilters] = useState<Filters>({});
  const [editing, setEditing] = useState<SourceItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form] = Form.useForm<SourceInput>();

  const items = data?.items ?? [];
  const visible = useMemo(() => {
    return items.filter((item) => {
      if (filters.category && !item.categories.includes(filters.category)) return false;
      if (filters.status === "enabled" && !item.enabled) return false;
      if (filters.status === "disabled" && item.enabled) return false;
      if (filters.status === "error" && item.error_count === 0) return false;
      if (filters.keyword) {
        const keyword = filters.keyword.toLowerCase();
        if (!item.name.toLowerCase().includes(keyword) && !item.url.toLowerCase().includes(keyword)) {
          return false;
        }
      }
      return true;
    });
  }, [items, filters]);

  function openCreate() {
    setEditing(null);
    form.setFieldsValue(EMPTY_FORM);
    setDrawerOpen(true);
  }

  function openEdit(item: SourceItem) {
    setEditing(item);
    form.setFieldsValue({
      name: item.name,
      url: item.url,
      feed_type: item.feed_type,
      lang: item.lang,
      enabled: item.enabled,
      categories: item.categories,
    });
    setDrawerOpen(true);
  }

  async function submit() {
    const values = await form.validateFields();
    try {
      if (editing) {
        await api.updateSource(editing.id, values);
        message.success("已保存");
      } else {
        await api.createSource(values);
        message.success("已新增");
      }
      setDrawerOpen(false);
      reload();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function test(item: SourceItem) {
    const result = await api.testSource(item.id);
    Modal.info({
      title: `${item.name} 测试结果`,
      width: 560,
      content: (
        <div>
          <p>{result.ok ? "抓取成功" : `抓取失败：${result.error ?? "未知原因"}`}</p>
          {result.preview.length ? (
            <ul>
              {result.preview.map((entry) => (
                <li key={entry.url}>{entry.title}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ),
    });
  }

  const columns = [
    {
      title: "采集源",
      key: "name",
      render: (_: unknown, row: SourceItem) => (
        <Space direction="vertical" size={0}>
          <span>{row.name}</span>
          <span className="aurora-muted">{row.url}</span>
        </Space>
      ),
    },
    {
      title: "板块",
      key: "categories",
      render: (_: unknown, row: SourceItem) => (
        <Space size={4} wrap>
          {row.categories.map((category) => (
            <Tag key={category} color={CATEGORY_MAP[category as keyof typeof CATEGORY_MAP]?.color}>
              {CATEGORY_MAP[category as keyof typeof CATEGORY_MAP]?.label ?? category}
            </Tag>
          ))}
        </Space>
      ),
    },
    { title: "类型", dataIndex: "feed_type", key: "feed_type" },
    { title: "语言", dataIndex: "lang", key: "lang" },
    {
      title: "健康",
      key: "health",
      render: (_: unknown, row: SourceItem) => {
        const level = HEALTH_LABELS[healthLevel(row)];
        return (
          <Tooltip title={row.last_error ?? `最近成功：${formatDateTime(row.last_ok_at)}`}>
            <Tag color={level.color}>
              {level.text}
              {row.error_count ? ` · ${row.error_count}` : ""}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "启用",
      key: "enabled",
      render: (_: unknown, row: SourceItem) => (
        <Switch
          size="small"
          checked={row.enabled}
          onChange={async (checked) => {
            await api.updateSource(row.id, { enabled: checked });
            reload();
          }}
        />
      ),
    },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, row: SourceItem) => (
        <Space size={4}>
          <Button size="small" onClick={() => test(row)}>
            测试
          </Button>
          <Button size="small" onClick={() => openEdit(row)}>
            编辑
          </Button>
          <Popconfirm
            title="删除该采集源？"
            onConfirm={async () => {
              await api.deleteSource(row.id);
              message.success("已删除");
              reload();
            }}
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="aurora-stack">
      <PageHeader
        title="采集源管理"
        tagline="白名单来源，关闭后不再参与采集"
        extra={
          <Button type="primary" onClick={openCreate}>
            + 新增源
          </Button>
        }
      />

      <Card size="small" variant="outlined">
        <Space wrap size={8} style={{ marginBottom: 12 }}>
          <Select
            allowClear
            size="small"
            placeholder="板块"
            style={{ width: 120 }}
            value={filters.category}
            onChange={(value) => setFilters((prev) => ({ ...prev, category: value }))}
            options={CATEGORY_OPTIONS}
          />
          <Select
            allowClear
            size="small"
            placeholder="状态"
            style={{ width: 120 }}
            value={filters.status}
            onChange={(value) => setFilters((prev) => ({ ...prev, status: value }))}
            options={[
              { label: "启用", value: "enabled" },
              { label: "已停用", value: "disabled" },
              { label: "有错误", value: "error" },
            ]}
          />
          <Input.Search
            allowClear
            size="small"
            placeholder="搜索名称或 URL"
            style={{ width: 240 }}
            onSearch={(value) => setFilters((prev) => ({ ...prev, keyword: value || undefined }))}
          />
        </Space>
        <Table size="small" rowKey="id" loading={loading} dataSource={visible} columns={columns} />
      </Card>

      <Drawer
        title={editing ? `编辑：${editing.name}` : "新增采集源"}
        width={460}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Space>
            <Button onClick={() => setDrawerOpen(false)}>取消</Button>
            <Button type="primary" onClick={submit}>
              保存并测试
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical" initialValues={EMPTY_FORM}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 Reuters Business" />
          </Form.Item>
          <Form.Item name="url" label="URL" rules={[{ required: true }]}>
            <Input placeholder="https://example.com/feed" />
          </Form.Item>
          <Form.Item name="feed_type" label="类型" rules={[{ required: true }]}>
            <Select options={FEED_TYPES} />
          </Form.Item>
          <Form.Item
            name="categories"
            label="板块"
            rules={[{ required: true, message: "至少选择一个板块" }]}
          >
            <Select mode="multiple" options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item name="lang" label="语言" rules={[{ required: true }]}>
            <Select options={LANGS} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
