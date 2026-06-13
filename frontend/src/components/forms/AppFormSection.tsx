import { useEffect } from "react";
import { Form, Input, Select } from "antd";
import { Plus } from "lucide-react";
import { AppButton } from "../actions/AppButton";

export type AppFormField = {
  name: string;
  label: string;
  area?: boolean;
  defaultValue?: string | number | boolean;
  initialValue?: string | number | boolean;
  min?: number;
  options?: Array<{ label: string; value: string }>;
  placeholder?: string;
  required?: boolean;
  step?: string;
  type?: string;
};

type AppFormSectionProps = {
  clearText?: string;
  fields: AppFormField[];
  loading?: boolean;
  onClear?: () => void;
  onSubmit: (payload: Record<string, unknown>, helpers: { reset: () => void }) => void;
  submitText?: string;
  title: string;
  values?: Record<string, unknown>;
};

export function AppFormSection({
  clearText = "清空",
  fields,
  loading,
  onClear,
  onSubmit,
  submitText = "保存",
  title,
  values,
}: AppFormSectionProps) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (values) form.setFieldsValue(values);
  }, [form, values]);

  return (
    <Form
      className="app-form-section"
      form={form}
      layout="vertical"
      onFinish={(formValues) => onSubmit(formValues, { reset: () => form.resetFields() })}
    >
      <div className="app-form-section-header"><h2>{title}</h2></div>
      <div className="app-form-section-grid">
        {fields.map((field) => (
          <Form.Item
            className={field.area ? "wide" : undefined}
            initialValue={field.initialValue ?? field.defaultValue}
            key={field.name}
            label={field.label}
            name={field.name}
            rules={field.required ? [{ required: true, message: `请填写${field.label}` }] : undefined}
          >
            {field.options ? (
              <Select options={field.options} />
            ) : field.area ? (
              <Input.TextArea placeholder={field.placeholder} rows={3} />
            ) : (
              <Input min={field.min} placeholder={field.placeholder} step={field.step} type={field.type} />
            )}
          </Form.Item>
        ))}
      </div>
      <div className="app-form-section-actions">
        <AppButton htmlType="submit" loading={loading} type="primary"><Plus size={16} />{submitText}</AppButton>
        {onClear && <AppButton onClick={() => { onClear(); form.resetFields(); }}>{clearText}</AppButton>}
      </div>
    </Form>
  );
}
