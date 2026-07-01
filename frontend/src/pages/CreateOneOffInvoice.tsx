import {
  Button,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
} from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import dayjs from "dayjs";
import { Invoices } from "../api/api";
import { CreateOneOffInvoiceType } from "../types/invoice-type";
import PricingUnitDropDown from "../components/PricingUnitDropDown";

type Params = {
  customerId: string;
  onSubmit: () => void;
  visible: boolean;
  onCancel: () => void;
};

function CreateOneOffInvoice({
  customerId,
  visible,
  onCancel,
  onSubmit,
}: Params) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const mutation = useMutation(
    (post: CreateOneOffInvoiceType) => Invoices.createOneOffInvoice(post),
    {
      onSuccess: () => {
        toast.success("Successfully created invoice", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["customer_detail", customerId]);
      },
      onError: () => {
        toast.error("Failed to create invoice", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const submit = () => {
    form
      .validateFields()
      .then((values) => {
        mutation.mutate({
          customer_id: customerId,
          currency_code: values.pricing_unit_code,
          issue_date: values.issue_date
            ? dayjs(values.issue_date).toISOString()
            : undefined,
          due_date: values.due_date
            ? dayjs(values.due_date).toISOString()
            : undefined,
          line_items: (values.line_items ?? []).map((li) => ({
            name: li.name,
            quantity: li.quantity ?? undefined,
            amount: li.amount,
            tax_rate: li.tax_rate ?? undefined,
          })),
        });
        onSubmit();
      })
      .catch(() => undefined);
  };

  return (
    <Modal
      width={1000}
      destroyOnClose
      title="Create One-Off Invoice"
      visible={visible}
      footer={[
        <Button key="back" onClick={onCancel}>
          Cancel
        </Button>,
        <Button key="submit" type="primary" onClick={submit}>
          Submit
        </Button>,
      ]}
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_one_off_invoice"
          initialValues={{
            pricing_unit_code: null,
            issue_date: null,
            due_date: null,
            line_items: [
              { name: "", quantity: null, amount: null, tax_rate: null },
            ],
          }}
          onFinish={submit}
          autoComplete="off"
          labelWrap
        >
          <div className="grid grid-cols-2 gap-4 p-4">
            <Form.Item
              rules={[{ required: true, message: "Please Select a currency" }]}
              name="pricing_unit_code"
              label="Currency"
            >
              <PricingUnitDropDown
                setCurrentCurrency={(value) =>
                  form.setFieldValue("pricing_unit_code", value)
                }
                setCurrentSymbol={() => null}
              />
            </Form.Item>
            <Form.Item
              valuePropName="date"
              name="issue_date"
              label="Issue Date"
            >
              <DatePicker
                onChange={(data) =>
                  form.setFieldValue("issue_date", dayjs(data))
                }
              />
            </Form.Item>
            <Form.Item valuePropName="date" name="due_date" label="Due Date">
              <DatePicker
                onChange={(data) => form.setFieldValue("due_date", dayjs(data))}
              />
            </Form.Item>
          </div>
          <div className="p-4">
            <Form.List name="line_items">
              {(fields, { add, remove }, { errors }) => (
                <>
                  {fields.map((field) => (
                    <div key={field.key} className="flex items-start space-x-4">
                      <Form.Item
                        {...field}
                        name={[field.name, "name"]}
                        rules={[{ required: true, message: "Name required" }]}
                        className="w-1/3"
                      >
                        <Input placeholder="Line item name" />
                      </Form.Item>
                      <Form.Item
                        {...field}
                        name={[field.name, "quantity"]}
                        className="w-1/6"
                      >
                        <InputNumber placeholder="Quantity" precision={2} />
                      </Form.Item>
                      <Form.Item
                        {...field}
                        name={[field.name, "amount"]}
                        rules={[
                          { required: true, message: "Amount required" },
                          {
                            validator(rule, value, callback) {
                              if (
                                value !== undefined &&
                                value !== null &&
                                value <= 0
                              ) {
                                callback("Value must be greater than 0");
                              } else {
                                callback();
                              }
                            },
                          },
                        ]}
                        className="w-1/6"
                      >
                        <InputNumber placeholder="Amount" precision={2} />
                      </Form.Item>
                      <Form.Item
                        {...field}
                        name={[field.name, "tax_rate"]}
                        className="w-1/6"
                        rules={[
                          {
                            validator(rule, value, callback) {
                              if (
                                value !== undefined &&
                                value !== null &&
                                value < 0
                              ) {
                                callback("Tax rate cannot be negative");
                              } else {
                                callback();
                              }
                            },
                          },
                        ]}
                      >
                        <InputNumber placeholder="Tax rate %" precision={3} />
                      </Form.Item>
                      {fields.length > 1 && (
                        <MinusCircleOutlined
                          className="mt-2"
                          onClick={() => remove(field.name)}
                        />
                      )}
                    </div>
                  ))}
                  <Form.Item>
                    <Button
                      type="dashed"
                      onClick={() => add()}
                      icon={<PlusOutlined />}
                    >
                      Add Line Item
                    </Button>
                  </Form.Item>
                  <Form.ErrorList errors={errors} />
                </>
              )}
            </Form.List>
          </div>
        </Form>
      </Form.Provider>
    </Modal>
  );
}

export default CreateOneOffInvoice;
