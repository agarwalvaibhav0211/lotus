import { LightweightCustomerType } from "./customer-type";
import { CurrencyType } from "./pricing-unit-type";

export interface InvoiceType {
  invoice_id: string;
  invoice_number: string;
  cost_due: number;
  currency: CurrencyType;
  issue_date: string;
  payment_status: "draft" | "paid" | "unpaid" | "voided";
  external_payment_obj_type: string;
  external_payment_obj_id: string;
  line_items: LineItem[];
  customer: LightweightCustomerType;
}

export interface DraftInvoiceType {
  invoices: IndividualDraftInvoiceType[];
}

export interface IndividualDraftInvoiceType {
  line_items: ExternalLineItem[];
  cost_due: number;
  issue_date: string;
  due_date: string;
  currency: {
    code: string;
    name: string;
    symbol: string;
  };
}

export interface ExternalLineItem {
  end_date: string;
  plan_name: string;
  start_date: string;
  base: number;
  subscription_filters?: { property_name: string; value: string }[];
  sub_items: LineItem[];
}

export interface LineItem {
  name: string;
  start_date: string;
  end_date: string;
  quantity: number;
  base: number;
  amount: number;
  adjustments: LineItemAdjustment[];
  billing_type: string;
  plan: string; // TODO::: fix
  metadata: object;
  subscription_filters: { property_name: string; value: string }[];
}

export interface LineItemAdjustment {
  amount: number;
  account: string;
  adjustment_type: string;
}

export interface MarkPaymentStatusAsPaid {
  invoice_id: string;
  payment_status: "paid" | "unpaid" | "voided";
}

export interface CreateOneOffInvoiceLineItemType {
  name: string;
  quantity?: number;
  amount: number;
  tax_rate?: number;
}

export interface CreateOneOffInvoiceType {
  customer_id: string;
  currency_code: string;
  issue_date?: string;
  due_date?: string;
  line_items: CreateOneOffInvoiceLineItemType[];
}
