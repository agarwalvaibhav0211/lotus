/* eslint-disable camelcase */
/* eslint-disable prefer-template */
/* eslint-disable no-nested-ternary */
import { Button, Dropdown, Menu, Table, Tag, Tooltip } from "antd";
import React, { FC, useEffect, useState } from "react";
import dayjs from "dayjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { MoreOutlined } from "@ant-design/icons";
import axios from "axios";
import { ProTable } from "@ant-design/pro-components";
import type { ProColumns } from "@ant-design/pro-components";
import { integrationsMap } from "../../types/payment-processor-type";
import { Invoices } from "../../api/api";
import { InvoiceType, MarkPaymentStatusAsPaid } from "../../types/invoice-type";
import { components } from "../../gen-types";
import CreateOneOffInvoice from "../../pages/CreateOneOffInvoice";

const InvoiceLineItemsBreakdown: FC<{ invoiceId: string }> = ({
  invoiceId,
}) => {
  const { data: invoice, isLoading } = useQuery<InvoiceType>(
    ["invoice_detail", invoiceId],
    () => Invoices.getInvoice(invoiceId)
  );

  if (isLoading) {
    return <p className="p-4">Loading line items...</p>;
  }

  if (!invoice || invoice.line_items.length === 0) {
    return <p className="p-4">No line items for this invoice</p>;
  }

  return (
    <Table
      dataSource={invoice.line_items}
      rowKey={(item) => `${item.name}-${item.start_date}-${item.end_date}`}
      pagination={false}
      columns={[
        { title: "Name", dataIndex: "name", key: "name" },
        { title: "Plan", dataIndex: "plan", key: "plan" },
        {
          title: "Period",
          key: "period",
          render: (_, item) =>
            `${dayjs(item.start_date).format("YYYY/MM/DD")} - ${dayjs(
              item.end_date
            ).format("YYYY/MM/DD")}`,
        },
        { title: "Quantity", dataIndex: "quantity", key: "quantity" },
        {
          title: "Billing Type",
          dataIndex: "billing_type",
          key: "billing_type",
        },
        {
          title: "Base",
          dataIndex: "base",
          key: "base",
          render: (base) => parseFloat(String(base)).toFixed(2),
        },
        {
          title: "Adjustments",
          dataIndex: "adjustments",
          key: "adjustments",
          render: (adjustments: InvoiceType["line_items"][0]["adjustments"]) =>
            adjustments && adjustments.length > 0
              ? adjustments
                  .map(
                    (adj) =>
                      `${adj.adjustment_type}: ${parseFloat(
                        String(adj.amount)
                      ).toFixed(2)}`
                  )
                  .join(", ")
              : "-",
        },
        {
          title: "Amount",
          dataIndex: "amount",
          key: "amount",
          render: (amount) => parseFloat(String(amount)).toFixed(2),
        },
      ]}
    />
  );
};

const PAID_STATUSES = ["paid", "settled", "succeeded", "completed"];
const PENDING_STATUSES = [
  "pending",
  "processing",
  "authorized",
  "submitted_for_settlement",
  "settling",
  "open",
  "draft",
];
const FAILED_STATUSES = [
  "failed",
  "unpaid",
  "voided",
  "void",
  "gateway_rejected",
  "processor_declined",
  "uncollectible",
  "expired",
];

const getStatusTagProps = (status: string | null | undefined) => {
  const normalized = (status || "").toLowerCase();
  let color = "default";
  if (PAID_STATUSES.includes(normalized)) {
    color = "green";
  } else if (PENDING_STATUSES.includes(normalized)) {
    color = "gold";
  } else if (FAILED_STATUSES.includes(normalized)) {
    color = "red";
  }
  return { color, label: (status || "").toUpperCase() };
};

const downloadFile = async (s3link) => {
  if (!s3link) {
    toast.error("No file to download");
    return;
  }
  window.open(s3link);
};

const getPdfUrl = async (
  invoice: components["schemas"]["CustomerDetail"]["invoices"][0]
) => {
  try {
    const response = await Invoices.getInvoiceUrl(invoice.invoice_id);
    const pdfUrl = response.url;
    downloadFile(pdfUrl);
  } catch (err) {
    toast.error("Error downloading file");
  }
};

const lotusUrl = new URL("./lotusIcon.svg", import.meta.url).href;

interface Props {
  customerId: string;
  invoices: components["schemas"]["CustomerDetail"]["invoices"] | undefined;
  paymentMethod: string;
}

const CustomerInvoiceView: FC<Props> = ({
  customerId,
  invoices,
  paymentMethod,
}) => {
  const queryClient = useQueryClient();
  const [showCreateInvoice, setShowCreateInvoice] = useState(false);
  const [selectedRecord, setSelectedRecord] =
    React.useState<components["schemas"]["CustomerDetail"]["invoices"][0]>();
  const changeStatus = useMutation(
    (post: MarkPaymentStatusAsPaid) => Invoices.changeStatus(post),
    {
      onSuccess: (data) => {
        const status = data.payment_status.toUpperCase();
        toast.success(`Successfully Changed Invoice Status to ${status}`, {
          position: toast.POSITION.TOP_CENTER,
        });
        selectedRecord.payment_status = data.payment_status;
      },
      onError: () => {
        toast.error("Failed to Changed Invoice Status", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const sendToPaymentProcessor = useMutation(
    (invoice_id: string) => Invoices.sendToPaymentProcessor(invoice_id),
    {
      onSuccess: (data) => {
        toast.success("Successfully sent to payment processor", {
          position: toast.POSITION.TOP_CENTER,
        });
        selectedRecord.external_payment_obj_type =
          data.external_payment_obj_type;
      },
      onError: () => {
        toast.error("Failed to send to payment processor", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  useEffect(() => {
    if (selectedRecord !== undefined) {
      changeStatus.mutate({
        invoice_id: selectedRecord.invoice_id,
        payment_status:
          selectedRecord.payment_status === "unpaid" ? "paid" : "unpaid",
      });
    }
  }, [selectedRecord]);

  const columns: ProColumns<
    components["schemas"]["CustomerDetail"]["invoices"][0]
  >[] = [
    {
      title: "Connections",
      dataIndex: "connections",
      width: 100,
      key: "connections",
      render: (_, record) => (
        <div className="flex gap-1">
          {record.external_payment_obj_type && (
            <Tooltip title={record.external_payment_obj_id}>
              {record.external_payment_obj_url ? (
                <a
                  href={record.external_payment_obj_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <img
                    className="sourceIcon"
                    src={
                      integrationsMap[
                        record.external_payment_obj_type as keyof typeof integrationsMap
                      ]?.icon || lotusUrl
                    }
                    alt={`${record.external_payment_obj_type} icon`}
                  />
                </a>
              ) : (
                <img
                  className="sourceIcon"
                  src={
                    integrationsMap[
                      record.external_payment_obj_type as keyof typeof integrationsMap
                    ]?.icon || lotusUrl
                  }
                  alt={`${record.external_payment_obj_type} icon`}
                />
              )}
            </Tooltip>
          )}
          {record.crm_provider && (
            <Tooltip title={record.crm_provider_id}>
              {record.crm_provider_url ? (
                <a
                  href={record.crm_provider_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <img
                    className="sourceIcon"
                    src={integrationsMap.salesforce.icon}
                    alt={`${record.crm_provider} icon`}
                  />
                </a>
              ) : (
                <img
                  className="sourceIcon"
                  src={
                    record.crm_provider === "salesforce"
                      ? integrationsMap.salesforce.icon
                      : lotusUrl
                  }
                  alt={`${record.crm_provider} icon`}
                />
              )}
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: "Invoice #",
      dataIndex: "invoice_number",
      key: "invoice_number",
    },
    {
      title: "Amount",
      dataIndex: "cost_due",
      key: "cost_due",
      render: (_, { cost_due, currency }) => (
        <span>
          {currency?.symbol}
          {parseFloat(String(cost_due)).toFixed(2)}
        </span>
      ),
    },
    {
      title: "Issue Date",
      dataIndex: "issue_date",
      key: "issue_date",
      render: (_, { issue_date }) => (
        <span>{dayjs(issue_date).format("YYYY/MM/DD")}</span>
      ),
    },
    {
      title: "Status",
      dataIndex: "payment_status",
      key: "status",
      render: (
        _,
        record: components["schemas"]["CustomerDetail"]["invoices"][0]
      ) => {
        const { color, label } = getStatusTagProps(
          record.external_payment_obj_status || record.payment_status
        );
        const statusTag = (
          <Tag color={color} key={label}>
            {label}
          </Tag>
        );
        return (
          <div className="flex">
            {record.external_payment_obj_type ? (
              <Tooltip
                title={
                  "Source: " +
                  (integrationsMap[
                    record.external_payment_obj_type as keyof typeof integrationsMap
                  ]?.name ?? record.external_payment_obj_type)
                }
              >
                {record.external_payment_obj_url ? (
                  <a
                    href={record.external_payment_obj_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {statusTag}
                  </a>
                ) : (
                  statusTag
                )}
              </Tooltip>
            ) : (
              statusTag
            )}

            <div
              className="ml-auto"
              aria-hidden
              onClick={(e) => e.stopPropagation()}
            >
              <Dropdown
                overlay={
                  <Menu>
                    <Menu.Item
                      key="1"
                      onClick={() => {
                        if ((import.meta as any).env.VITE_IS_DEMO === "true") {
                          toast.error("This feature is disabled in the demo", {
                            position: toast.POSITION.TOP_CENTER,
                          });
                        } else {
                          getPdfUrl(record);
                        }
                      }}
                    >
                      <div className="archiveLabel">Download Invoice PDF</div>
                    </Menu.Item>
                    {!record.external_payment_obj_type &&
                      record.payment_status === "unpaid" && (
                        <Menu.Item
                          key="2"
                          onClick={() => {
                            if (
                              (import.meta as any).env.VITE_IS_DEMO === "true"
                            ) {
                              toast.error(
                                "This feature is disabled in the demo",
                                {
                                  position: toast.POSITION.TOP_CENTER,
                                }
                              );
                            } else if (selectedRecord === record) {
                              changeStatus.mutate({
                                invoice_id: record.invoice_id,
                                payment_status: "paid",
                              });
                            } else {
                              setSelectedRecord(record);
                            }
                          }}
                        >
                          <div className="archiveLabel">Mark As Paid</div>
                        </Menu.Item>
                      )}
                    {!record.external_payment_obj_type &&
                      paymentMethod &&
                      record.payment_status === "unpaid" && (
                        <Menu.Item
                          key="2"
                          onClick={() => {
                            if (selectedRecord === record) {
                              sendToPaymentProcessor.mutate(record.invoice_id);
                            } else {
                              setSelectedRecord(record);
                            }
                          }}
                        >
                          <div className="archiveLabel">
                            Send to Payment Processor
                          </div>
                        </Menu.Item>
                      )}
                  </Menu>
                }
                trigger={["click"]}
              >
                <Button
                  type="text"
                  size="small"
                  onClick={(e) => e.preventDefault()}
                >
                  <MoreOutlined />
                </Button>
              </Dropdown>
            </div>
          </div>
        );
      },
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="mb-2 pb-4 pt-4 font-bold text-main">Invoices</h2>
        <Button
          type="primary"
          className="hover:!bg-primary-700"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
          disabled={(import.meta as any).env.VITE_IS_DEMO === "true"}
          onClick={() => setShowCreateInvoice(true)}
        >
          Create Invoice
        </Button>
      </div>
      {showCreateInvoice && (
        <CreateOneOffInvoice
          customerId={customerId}
          visible={showCreateInvoice}
          onCancel={() => setShowCreateInvoice(false)}
          onSubmit={() => {
            setShowCreateInvoice(false);
            queryClient.invalidateQueries(["customer_detail", customerId]);
          }}
        />
      )}
      {invoices !== undefined ? (
        <ProTable
          columns={columns}
          dataSource={invoices}
          rowKey="invoice_id"
          pagination={{
            showTotal: (total, range) => (
              <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
            ),
            pageSize: 8,
          }}
          options={false}
          toolBarRender={false}
          search={false}
          expandable={{
            expandedRowRender: (record) => (
              <InvoiceLineItemsBreakdown invoiceId={record.invoice_id} />
            ),
          }}
        />
      ) : (
        <p>No invoices found</p>
      )}
    </div>
  );
};

export default CustomerInvoiceView;
