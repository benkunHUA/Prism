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
      <Form.Item name="name" label={SOURCE_TEXT.nameLabel} rules={[{ required: true }]}>
        <Input placeholder={SOURCE_TEXT.namePlaceholder} />
      </Form.Item>
      <Form.Item name="url" label={SOURCE_TEXT.urlLabel} rules={[{ required: true }]}>
        <Input placeholder={SOURCE_TEXT.urlPlaceholder} />
      </Form.Item>
      <Form.Item name="feed_type" label={SOURCE_TEXT.feedTypeLabel} rules={[{ required: true }]}>
        <Select options={FEED_TYPES} />
      </Form.Item>
      <Form.Item
        name="categories"
        label={SOURCE_TEXT.categoriesLabel}
        rules={[{ required: true, message: SOURCE_TEXT.categoriesRequired }]}
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
      <Form.Item name="lang" label={SOURCE_TEXT.langLabel} rules={[{ required: true }]}>
        <Select options={LANGS} />
      </Form.Item>
      <Form.Item name="enabled" label={SOURCE_TEXT.enabledLabel} valuePropName="checked">
        <Switch />
      </Form.Item>
    </Form>
  );
}
