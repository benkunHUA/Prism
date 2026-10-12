import { Form, Input, Select, Switch } from "antd";
import type { FormInstance } from "antd";

import type { RegionOption, SourceInput } from "../../api/types";
import { CATEGORY_OPTIONS } from "../../constants/categories";
import { FEED_TYPES, LANGS } from "../../constants/options";
import { EMPTY_SOURCE_FORM, SOURCE_TEXT, regionSelectOptions } from "../../constants/sources";

interface SourceFormProps {
  form: FormInstance<SourceInput>;
  regions: RegionOption[];
  regionsLoading?: boolean;
}

export default function SourceForm({ form, regions, regionsLoading }: SourceFormProps) {
  return (
    <Form form={form} layout="vertical" initialValues={EMPTY_SOURCE_FORM}>
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
      <Form.Item
        name="region"
        label={SOURCE_TEXT.regionLabel}
        tooltip={SOURCE_TEXT.regionTooltip}
        // 表单值保持后端契约里的空串，展示上空串等同于未选择
        normalize={(value: string | undefined) => value ?? ""}
        getValueProps={(value: string) => ({ value: value || undefined })}
      >
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder={SOURCE_TEXT.regionPlaceholder}
          loading={regionsLoading}
          options={regionSelectOptions(regions)}
        />
      </Form.Item>
      <Form.Item name="lang" label="语言" rules={[{ required: true }]}>
        <Select options={LANGS} />
      </Form.Item>
      <Form.Item name="enabled" label="启用" valuePropName="checked">
        <Switch />
      </Form.Item>
    </Form>
  );
}
