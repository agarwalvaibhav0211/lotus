import React, { FC, useState } from "react";
import { Button, Modal, Input, Table } from "antd";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "react-toastify";
import { Features } from "../api/api";
import { CreateFeatureType, FeatureType } from "../types/feature-type";
import LoadingSpinner from "../components/LoadingSpinner";
import { PageLayout } from "../components/base/PageLayout";
import { PlusOutlined } from "@ant-design/icons";

const defaultFeatureState: CreateFeatureType = {
  feature_name: "",
  feature_description: "",
};

const ViewFeatures: FC = () => {
  const [visible, setVisible] = useState<boolean>(false);
  const [featureState, setFeatureState] =
    useState<CreateFeatureType>(defaultFeatureState);
  const [editingFeature, setEditingFeature] = useState<FeatureType | null>(
    null
  );

  const queryClient = useQueryClient();

  const { data, isLoading, isError }: UseQueryResult<FeatureType[]> = useQuery<
    FeatureType[]
  >(["feature_list"], () => Features.getFeatures().then((res) => res));

  const mutation = useMutation(
    (post: CreateFeatureType) => Features.createFeature(post),
    {
      onSuccess: () => {
        setVisible(false);
        queryClient.invalidateQueries(["feature_list"]);
        toast.success("Successfully created feature", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onMutate: () => {
        toast.loading("Creating feature...", {
          position: toast.POSITION.TOP_CENTER,
          autoClose: false,
        });
      },
      onError: (error: any) => {
        toast.error(`Error creating feature: ${error.response.data.detail}`, {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onSettled: () => {
        toast.dismiss();
      },
    }
  );

  const updateMutation = useMutation(
    ({ feature_id, patch }: { feature_id: string; patch: CreateFeatureType }) =>
      Features.updateFeature(feature_id, patch),
    {
      onSuccess: () => {
        setVisible(false);
        setEditingFeature(null);
        queryClient.invalidateQueries(["feature_list"]);
        toast.success("Successfully updated feature", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onMutate: () => {
        toast.loading("Updating feature...", {
          position: toast.POSITION.TOP_CENTER,
          autoClose: false,
        });
      },
      onError: (error: any) => {
        toast.error(`Error updating feature: ${error.response.data.detail}`, {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onSettled: () => {
        toast.dismiss();
      },
    }
  );

  const createFeatureButton = () => {
    setEditingFeature(null);
    setFeatureState(defaultFeatureState);
    setVisible(true);
  };

  const editFeatureButton = (feature: FeatureType) => {
    setEditingFeature(feature);
    setFeatureState({
      feature_name: feature.feature_name,
      feature_description: feature.feature_description ?? "",
    });
    setVisible(true);
  };

  const onCancel = () => {
    setVisible(false);
    setEditingFeature(null);
  };

  const onSave = () => {
    if (editingFeature) {
      updateMutation.mutate({
        feature_id: editingFeature.feature_id,
        patch: featureState,
      });
    } else {
      mutation.mutate(featureState);
    }
  };

  return (
    <PageLayout
      title="Features"
      extra={[
        <Button
          type="primary"
          size="large"
          id="create-feature-button"
          key={"create-feature"}
          onClick={createFeatureButton}
          className="hover:!bg-primary-700"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          <div className="flex items-center justify-between text-white">
            <div>
              <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
              Create Feature
            </div>
          </div>
        </Button>,
      ]}
    >
      <div className="flex flex-col space-y-4">
        {isLoading || data === undefined ? (
          <div className="flex align-center justify-center min-h-[100px] bg-white">
            <LoadingSpinner />
          </div>
        ) : (
          <Table
            dataSource={data}
            rowKey="feature_id"
            columns={[
              {
                title: "Name",
                dataIndex: "feature_name",
                key: "feature_name",
              },
              {
                title: "Description",
                dataIndex: "feature_description",
                key: "feature_description",
              },
              {
                title: "",
                key: "actions",
                width: 100,
                render: (_, record: FeatureType) => (
                  <Button
                    type="link"
                    className="!p-0"
                    onClick={() => editFeatureButton(record)}
                  >
                    Edit
                  </Button>
                ),
              },
            ]}
          />
        )}
        {isError && <div className=" text-danger">Something went wrong</div>}
      </div>
      <Modal
        title={editingFeature ? "Edit Feature" : "Create Feature"}
        visible={visible}
        onCancel={onCancel}
        onOk={onSave}
        okButtonProps={{ disabled: !featureState.feature_name.trim() }}
      >
        {editingFeature && (
          <div className="mb-4 text-sm text-gold">
            Renaming applies everywhere this feature is used, including plan
            versions already live with customers.
          </div>
        )}
        <div className="flex flex-col space-y-4">
          <div>
            <label className="block mb-1">Name</label>
            <Input
              value={featureState.feature_name}
              onChange={(e) =>
                setFeatureState({
                  ...featureState,
                  feature_name: e.target.value,
                })
              }
            />
          </div>
          <div>
            <label className="block mb-1">Description</label>
            <Input.TextArea
              value={featureState.feature_description}
              onChange={(e) =>
                setFeatureState({
                  ...featureState,
                  feature_description: e.target.value,
                })
              }
            />
          </div>
        </div>
      </Modal>
    </PageLayout>
  );
};

export default ViewFeatures;
