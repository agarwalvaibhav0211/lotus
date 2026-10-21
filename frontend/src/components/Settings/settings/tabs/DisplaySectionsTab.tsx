import React, { FC, useState } from "react";
import { Button, Modal, Input, InputNumber, Table } from "antd";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "react-toastify";
import { PlusOutlined } from "@ant-design/icons";
import { DisplaySections } from "../../../../api/api";
import {
  CreateDisplaySectionType,
  DisplaySectionType,
} from "../../../../types/display-section-type";
import LoadingSpinner from "../../../LoadingSpinner";

const defaultSectionState: CreateDisplaySectionType = {
  name: "",
  description: "",
  sort_order: 0,
};

const DisplaySectionsTab: FC = () => {
  const [visible, setVisible] = useState<boolean>(false);
  const [sectionState, setSectionState] =
    useState<CreateDisplaySectionType>(defaultSectionState);
  const [editingSection, setEditingSection] =
    useState<DisplaySectionType | null>(null);

  const queryClient = useQueryClient();

  const { data, isLoading, isError }: UseQueryResult<DisplaySectionType[]> =
    useQuery<DisplaySectionType[]>(["display_section_list"], () =>
      DisplaySections.getDisplaySections().then((res) => res)
    );

  const invalidate = () =>
    queryClient.invalidateQueries(["display_section_list"]);

  const createMutation = useMutation(
    (post: CreateDisplaySectionType) =>
      DisplaySections.createDisplaySection(post),
    {
      onSuccess: () => {
        setVisible(false);
        invalidate();
        toast.success("Successfully created display section", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: (error: any) => {
        toast.error(
          `Error creating display section: ${
            error.response?.data?.detail ?? "unknown error"
          }`,
          { position: toast.POSITION.TOP_CENTER }
        );
      },
    }
  );

  const updateMutation = useMutation(
    ({
      section_id,
      patch,
    }: {
      section_id: string;
      patch: CreateDisplaySectionType;
    }) => DisplaySections.updateDisplaySection(section_id, patch),
    {
      onSuccess: () => {
        setVisible(false);
        setEditingSection(null);
        invalidate();
        toast.success("Successfully updated display section", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: (error: any) => {
        toast.error(
          `Error updating display section: ${
            error.response?.data?.detail ?? "unknown error"
          }`,
          { position: toast.POSITION.TOP_CENTER }
        );
      },
    }
  );

  const deleteMutation = useMutation(
    (section_id: string) => DisplaySections.deleteDisplaySection(section_id),
    {
      onSuccess: () => {
        invalidate();
        toast.success("Successfully deleted display section", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Error deleting display section", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const createButton = () => {
    setEditingSection(null);
    setSectionState(defaultSectionState);
    setVisible(true);
  };

  const editButton = (section: DisplaySectionType) => {
    setEditingSection(section);
    setSectionState({
      name: section.name,
      description: section.description ?? "",
      sort_order: section.sort_order,
    });
    setVisible(true);
  };

  const onDelete = (section: DisplaySectionType) => {
    Modal.confirm({
      title: `Delete "${section.name}"?`,
      content:
        "Features and metrics in this section will become unsectioned. This cannot be undone.",
      okText: "Delete",
      okButtonProps: { danger: true },
      onOk: () => deleteMutation.mutate(section.section_id),
    });
  };

  const onCancel = () => {
    setVisible(false);
    setEditingSection(null);
  };

  const onSave = () => {
    if (editingSection) {
      updateMutation.mutate({
        section_id: editingSection.section_id,
        patch: sectionState,
      });
    } else {
      createMutation.mutate(sectionState);
    }
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex justify-end">
        <Button
          type="primary"
          onClick={createButton}
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          <div className="flex items-center text-white">
            <PlusOutlined className="!text-white mr-1" />
            Create Section
          </div>
        </Button>
      </div>
      {isLoading || data === undefined ? (
        <div className="flex align-center justify-center min-h-[100px] bg-white">
          <LoadingSpinner />
        </div>
      ) : (
        <Table
          dataSource={data}
          rowKey="section_id"
          pagination={false}
          columns={[
            {
              title: "Order",
              dataIndex: "sort_order",
              key: "sort_order",
              width: 80,
            },
            {
              title: "Name",
              dataIndex: "name",
              key: "name",
            },
            {
              title: "Description",
              dataIndex: "description",
              key: "description",
            },
            {
              title: "",
              key: "actions",
              width: 150,
              render: (_, record: DisplaySectionType) => (
                <div className="flex space-x-4">
                  <Button
                    type="link"
                    className="!p-0"
                    onClick={() => editButton(record)}
                  >
                    Edit
                  </Button>
                  <Button
                    type="link"
                    danger
                    className="!p-0"
                    onClick={() => onDelete(record)}
                  >
                    Delete
                  </Button>
                </div>
              ),
            },
          ]}
        />
      )}
      {isError && <div className="text-danger">Something went wrong</div>}
      <Modal
        title={
          editingSection ? "Edit Display Section" : "Create Display Section"
        }
        visible={visible}
        onCancel={onCancel}
        onOk={onSave}
        okButtonProps={{ disabled: !sectionState.name.trim() }}
      >
        <div className="flex flex-col space-y-4">
          <div>
            <label className="block mb-1">Name</label>
            <Input
              value={sectionState.name}
              onChange={(e) =>
                setSectionState({ ...sectionState, name: e.target.value })
              }
            />
          </div>
          <div>
            <label className="block mb-1">Description</label>
            <Input.TextArea
              value={sectionState.description ?? ""}
              onChange={(e) =>
                setSectionState({
                  ...sectionState,
                  description: e.target.value,
                })
              }
            />
          </div>
          <div>
            <label className="block mb-1">Order</label>
            <InputNumber
              style={{ width: "100%" }}
              value={sectionState.sort_order}
              onChange={(value) =>
                setSectionState({ ...sectionState, sort_order: value ?? 0 })
              }
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default DisplaySectionsTab;
