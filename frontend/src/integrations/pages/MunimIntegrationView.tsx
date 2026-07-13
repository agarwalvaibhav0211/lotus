import React, { FC, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input, Modal } from "antd";
import { useMutation } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { PageLayout } from "../../components/base/PageLayout";
import CopyText from "../../components/base/CopytoClipboard";
import {
  PaymentProcessorIntegration,
  PaymentProcessor,
  Organization,
  API_HOST,
} from "../../api/api";
import {
  Source,
  PaymentProcessorImportCustomerResponse,
  PaymentProcessorConnectionRequestType,
  PaymentProcessorConnectionResponseType,
} from "../../types/payment-processor-type";
import useGlobalStore from "../../stores/useGlobalstore";
import { components } from "../../gen-types";

const TOAST_POSITION = toast.POSITION.TOP_CENTER;

const MunimIntegrationView: FC = () => {
  const navigate = useNavigate();
  const [apiKey, setApiKey] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSettingValue, setIsSettingValue] = useState(false);
  const [webhookInfo, setWebhookInfo] = useState<{
    url: string;
    secret: string;
  } | null>(null);
  const [genCustomerInMunimSetting, setGenCustomerInMunimSetting] =
    useState<boolean>();
  const org = useGlobalStore((state) => state.org);
  const setOrgInfoToStore = useGlobalStore((state) => state.setOrgInfo);
  useEffect(() => {
    setGenCustomerInMunimSetting(org?.gen_cust_in_munim_after_lotus);
  }, []);

  const connectMutation = useMutation(
    (post: PaymentProcessorConnectionRequestType) =>
      PaymentProcessorIntegration.connectPaymentProcessor(post),
    {
      onSuccess: (data: PaymentProcessorConnectionResponseType) => {
        toast.success("Successfully connected to Munim", {
          position: TOAST_POSITION,
        });
        setIsConnecting(false);
        if (data.webhook_secret && data.webhook_path) {
          setWebhookInfo({
            url: `${API_HOST.replace(/\/$/, "")}${data.webhook_path}`,
            secret: data.webhook_secret,
          });
        }
      },
      onError: () => {
        toast.error("Failed to connect to Munim. Check that your API key is valid.", {
          position: TOAST_POSITION,
        });
        setIsConnecting(false);
      },
    },
  );

  const regenerateWebhookSecretMutation = useMutation(
    () => PaymentProcessorIntegration.regenerateMunimWebhookSecret(),
    {
      onSuccess: (data) => {
        toast.success("Munim webhook secret generated", {
          position: TOAST_POSITION,
        });
        setWebhookInfo({
          url: `${API_HOST.replace(/\/$/, "")}${data.webhook_path}`,
          secret: data.webhook_secret,
        });
      },
      onError: () => {
        toast.error(
          "Failed to regenerate webhook secret. Make sure Munim is connected.",
          { position: TOAST_POSITION },
        );
      },
    },
  );

  const importCustomersMutation = useMutation(
    (post: Source) => PaymentProcessor.importCustomers(post),
    {
      onSuccess: (data: PaymentProcessorImportCustomerResponse) => {
        toast.success(data.detail, { position: TOAST_POSITION });
      },
      onError: () => {
        toast.error("Failed to Import Customers", { position: TOAST_POSITION });
      },
    },
  );

  const updateGenCustomerInMunimSetting = useMutation(
    (genCustomerInMunimSettingValue: boolean) => {
      if (org?.organization_id) {
        return Organization.updateOrganization(org.organization_id, {
          gen_cust_in_munim_after_lotus: genCustomerInMunimSettingValue,
        });
      }
      throw new Error("Organization ID is undefined");
    },
    {
      onSuccess: (data: components["schemas"]["Organization"]) => {
        setOrgInfoToStore(data);
        setGenCustomerInMunimSetting(data.gen_cust_in_munim_after_lotus);
        setIsSettingValue(false);
        const state =
          data.gen_cust_in_munim_after_lotus === true ? "Enabled" : "Disabled";
        toast.success(`${state} Create Lotus Customers In Munim`, {
          position: TOAST_POSITION,
        });
      },
      onError: () => {
        setIsSettingValue(false);
        toast.error("Failed to Update Create Lotus Customers In Munim", {
          position: TOAST_POSITION,
        });
      },
    },
  );

  const handleConnect = () => {
    if (!apiKey) {
      toast.error("Enter your Munim API key first", {
        position: TOAST_POSITION,
      });
      return;
    }
    setIsConnecting(true);
    const ppInfo: PaymentProcessorConnectionRequestType = {
      payment_processor: "munim",
      data: { api_key: apiKey },
    };
    connectMutation.mutate(ppInfo);
  };

  return (
    <PageLayout
      title="Munim Integration"
      extra={<Button onClick={() => navigate(-1)}>Back to Integrations</Button>}
    >
      <div className="w-6/12">
        <h2 className="text-16px mb-10">
          Charge and invoice your customers through your Munim account
        </h2>
        <div className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-6 py-10">
          <h3>Munim API Key:</h3>
          <Input.Password
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your Munim API key"
          />
          <h3>Connect Munim:</h3>
          <Button type="primary" loading={isConnecting} onClick={handleConnect}>
            Connect
          </Button>
          <h3>Munim Webhook:</h3>
          <Button
            loading={regenerateWebhookSecretMutation.isLoading}
            onClick={() => regenerateWebhookSecretMutation.mutate()}
          >
            Get / Regenerate Webhook Secret
          </Button>
          <h3>Import Munim Customers:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => {
              const promise = importCustomersMutation.mutateAsync({
                source: "munim",
              });
              toast.promise(promise, {
                pending: "Importing Customers From Munim",
              });
            }}
          >
            Import
          </Button>
          <h3>Create Lotus Customers In Munim:</h3>
          <div className="flex h-6 items-center">
            <input
              id="gen-cust-in-munim"
              aria-describedby="gen-cust-in-munim-description"
              name="gen-cust-in-munim"
              type="checkbox"
              disabled={isSettingValue}
              checked={genCustomerInMunimSetting === true}
              onChange={(value) => {
                updateGenCustomerInMunimSetting.mutate(value.target.checked);
                setIsSettingValue(true);
              }}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>
      <Modal
        title="Munim Webhook Details"
        visible={webhookInfo !== null}
        onCancel={() => setWebhookInfo(null)}
        onOk={() => setWebhookInfo(null)}
        footer={<Button onClick={() => setWebhookInfo(null)}>Done</Button>}
      >
        <p className="mb-4">
          Configure Munim to call this URL when a payment completes, using the
          secret below as a Bearer token. This secret will only be shown once
          &mdash; regenerating it invalidates any previous secret.
        </p>
        <div className="mb-4">
          <h3 className="mb-1">Webhook URL:</h3>
          <CopyText textToCopy={webhookInfo?.url ?? ""} />
        </div>
        <div>
          <h3 className="mb-1">Webhook Secret:</h3>
          <CopyText textToCopy={webhookInfo?.secret ?? ""} />
        </div>
      </Modal>
    </PageLayout>
  );
};

export default MunimIntegrationView;
