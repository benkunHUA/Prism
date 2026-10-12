import { Button, Card, Drawer, Input, InputNumber, Select, Space, Tag, message } from "antd";
import { useState } from "react";

import { api } from "../api/endpoints";
import type { ModerationItem } from "../api/types";
import { CATEGORY_OPTIONS } from "../constants/categories";
import { IMPORTANCE_OPTIONS, STANCE_TONES, TEXT, WEAPON_LIFECYCLE } from "../constants/options";
import { useAsync } from "../hooks/useAsync";
import { draftFrom, editPayload, moderationFields, moderationTitle, type ModerationEditDraft } from "../utils/moderation";

import EmptyHint from "../components/EmptyHint";

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}

const TYPE_ORDER = ["timeline", "weapon", "stance", "indicator"] as const;
const TYPE_LABELS: Record<string, string> = {
  timeline: "事件",
  weapon: "武器",
  stance: "立场",
  indicator: "指标",
};

function EditForm({
  item,
  draft,
  onChange,
}: {
  item: ModerationItem;
  draft: ModerationEditDraft;
  onChange: (next: ModerationEditDraft) => void;
}) {
  if (item.type === "timeline") {
    return (
      <Space direction="vertical" style={{ width: "100%" }} size={6}>
        <Input.TextArea
          rows={2}
          value={draft.summary}
          onChange={(e) => onChange({ ...draft, summary: e.target.value })}
        />
        <Select
          size="small"
          value={draft.importance}
          onChange={(value) => onChange({ ...draft, importance: value })}
          options={IMPORTANCE_OPTIONS}
        />
      </Space>
    );
  }
  if (item.type === "weapon") {
    return (
      <Space direction="vertical" style={{ width: "100%" }} size={6}>
        <Input.TextArea
          rows={2}
          value={draft.params_text}
          onChange={(e) => onChange({ ...draft, params_text: e.target.value })}
        />
        <Select
          size="small"
          value={draft.lifecycle_status}
          onChange={(value) => onChange({ ...draft, lifecycle_status: value })}
          options={WEAPON_LIFECYCLE}
        />
      </Space>
    );
  }
  if (item.type === "stance") {
    return (
      <Space direction="vertical" style={{ width: "100%" }} size={6}>
        <Input.TextArea
          rows={2}
          value={draft.stance_text}
          onChange={(e) => onChange({ ...draft, stance_text: e.target.value })}
        />
        <Select
          size="small"
          value={draft.tone}
          onChange={(value) => onChange({ ...draft, tone: value })}
          options={STANCE_TONES}
        />
      </Space>
    );
  }
  return (
    <InputNumber
      value={draft.value === "" ? null : Number(draft.value)}
      onChange={(value) => onChange({ ...draft, value: value === null ? "" : String(value) })}
    />
  );
}

export default function ModerationDrawer({ open, onClose, onChanged }: Props) {
  const [filter, setFilter] = useState<string | undefined>(undefined);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<ModerationEditDraft | null>(null);

  const { data, loading, reload } = useAsync(() => api.moderations(filter), [filter]);
  const items = data?.items ?? [];

  async function apply(item: ModerationItem, body: Parameters<typeof api.moderate>[2]) {
    try {
      await api.moderate(item.type, item.id, body);
      message.success("已更新");
      setEditingKey(null);
      setDraft(null);
      reload();
      onChanged();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  return (
    <Drawer
      title={`${TEXT.moderation}队列（${items.length}）`}
      placement="right"
      width={560}
      open={open}
      onClose={onClose}
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Space>
          <span className="aurora-muted">板块</span>
          <Select
            allowClear
            size="small"
            placeholder="全部板块"
            style={{ width: 140 }}
            value={filter}
            onChange={setFilter}
            options={CATEGORY_OPTIONS}
          />
          <Button size="small" onClick={reload}>
            {TEXT.refresh}
          </Button>
        </Space>

        {!loading && items.length === 0 ? <EmptyHint text="没有待确认条目" compact /> : null}

        {TYPE_ORDER.map((type) => {
          const group = items.filter((item) => item.type === type);
          if (!group.length) return null;
          return (
            <Card
              key={type}
              size="small"
              variant="outlined"
              title={`${TYPE_LABELS[type]}（${group.length}）`}
            >
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                {group.map((item) => {
                  const key = `${item.type}-${item.id}`;
                  const isEditing = editingKey === key && draft !== null;
                  return (
                    <Card key={key} size="small" type="inner">
                      <Space direction="vertical" size={6} style={{ width: "100%" }}>
                        <Space size={6} wrap>
                          <Tag color="orange">{TYPE_LABELS[item.type]}</Tag>
                          <span>{moderationTitle(item)}</span>
                        </Space>
                        {!isEditing
                          ? moderationFields(item).map((field) => (
                              <div key={field.label}>
                                <span className="aurora-muted">{field.label}：</span>
                                {field.value}
                              </div>
                            ))
                          : null}
                        {isEditing && draft ? (
                          <EditForm item={item} draft={draft} onChange={setDraft} />
                        ) : null}
                        <Space size={6}>
                          <Button
                            size="small"
                            type="primary"
                            onClick={() => apply(item, { action: "confirm" })}
                          >
                            {TEXT.confirm}
                          </Button>
                          {isEditing ? (
                            <>
                              <Button
                                size="small"
                                onClick={() => apply(item, editPayload(item, draft as ModerationEditDraft))}
                              >
                                {TEXT.save}
                              </Button>
                              <Button
                                size="small"
                                onClick={() => {
                                  setEditingKey(null);
                                  setDraft(null);
                                }}
                              >
                                {TEXT.cancel}
                              </Button>
                            </>
                          ) : (
                            <Button
                              size="small"
                              onClick={() => {
                                setEditingKey(key);
                                setDraft(draftFrom(item));
                              }}
                            >
                              {TEXT.edit}
                            </Button>
                          )}
                          <Button size="small" danger onClick={() => apply(item, { action: "reject" })}>
                            {TEXT.reject}
                          </Button>
                        </Space>
                      </Space>
                    </Card>
                  );
                })}
              </Space>
            </Card>
          );
        })}
      </Space>
    </Drawer>
  );
}
