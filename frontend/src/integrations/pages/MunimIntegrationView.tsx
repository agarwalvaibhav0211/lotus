import React, { FC, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "antd";
import { useMutation } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { PageLayout } from "../../components/base/PageLayout";
import { PaymentProcessorIntegration, PaymentProcessor } from "../../api/api";
import {
  Source,
  PaymentProcessorImportCustomerResponse,
  PaymentProcessorConnectionRequestType,
} from "../../types/payment-processor-type";

const TOAST_POSITION = toast.POSITION.TOP_CENTER;

const MunimIntegrationView: FC = () => {
  const navigate = useNavigate();
  const [isConnecting, setIsConnecting] = useState(false);

  const connectMutation = useMutation(
    (post: PaymentProcessorConnectionRequestType) =>
      PaymentProcessorIntegration.connectPaymentProcessor(post),
    {
      onSuccess: () => {
        toast.success("Successfully connected to Munim", {
          position: TOAST_POSITION,
        });
        setIsConnecting(false);
      },
      onError: () => {
        toast.error(
          "Failed to connect to Munim. Ensure MUNIM_API_KEY is set on the server.",
          {
            position: TOAST_POSITION,
          },
        );
        setIsConnecting(false);
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

  const handleConnect = () => {
    setIsConnecting(true);
    const ppInfo: PaymentProcessorConnectionRequestType = {
      payment_processor: "munim",
      data: {},
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
          <h3>Connect Munim:</h3>
          <Button type="primary" loading={isConnecting} onClick={handleConnect}>
            Connect
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
        </div>
      </div>
    </PageLayout>
  );
};

export default MunimIntegrationView;
