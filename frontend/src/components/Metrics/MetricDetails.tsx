import { Modal, Tag, Button, Input, InputNumber, Select } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import React, { FC, useState } from "react";
import { format } from "sql-formatter";
import {
  MetricType,
  MetricDisplayFormats,
  UpdateMetricDisplayType,
} from "../../types/metric-type";
import { DisplaySectionType } from "../../types/display-section-type";
import { Metrics, DisplaySections } from "../../api/api";
import { colorMap } from "./MetricTable";
import createShortenedText from "../../helpers/createShortenedText";
import CopyText from "../base/CopytoClipboard";
import useMediaQuery from "../../hooks/useWindowQuery";

interface MetricDetailsProps {
  metric: MetricType;
  onclose: () => void;
}
const operatorDisplayMap = new Map<string, string>([
  ["eq", "="],
  ["isin", "in"],
  ["gt", ">"],
  ["gte", ">="],
  ["lt", "<"],
  ["lte", "<="],
  ["isnotin", "not in"],
]);

const MetricDetails: FC<MetricDetailsProps> = ({ metric, onclose }) => {
  const queryClient = useQueryClient();
  const windowWidth = useMediaQuery();

  const [displayState, setDisplayState] = useState<UpdateMetricDisplayType>({
    display_name: metric.display_name ?? "",
    display_description: metric.display_description ?? "",
    display_format: metric.display_format ?? null,
    display_unit: metric.display_unit ?? "",
    display_section_id: metric.display_section?.section_id ?? null,
    display_order: metric.display_order ?? 0,
  });

  const { data: sections } = useQuery<DisplaySectionType[]>(
    ["display_section_list"],
    () => DisplaySections.getDisplaySections().then((res) => res)
  );

  const formattedSQL = metric.custom_sql
    ? format(metric.custom_sql, { language: "postgresql" })
    : "";
  const mutation = useMutation(
    (metric_id: string) => Metrics.archiveMetric(metric_id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["metric_list"]);
        toast.success("Metric archived");
        onclose();
      },

      onError: (error: any) => {
        toast.error(error.response.data.detail);
      },
    }
  );

  const displayMutation = useMutation(
    (patch: UpdateMetricDisplayType) =>
      Metrics.updateMetric(metric.metric_id, patch),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["metric_list"]);
        toast.success("Updated pricing page display settings");
      },
      onError: (error: any) => {
        toast.error(
          error.response?.data?.detail ?? "Failed to update display settings"
        );
      },
    }
  );
  return (
    <Modal
      visible
      title={<b> {metric?.metric_name ? metric.metric_name : "Metric"} </b>}
      footer={[
        <Button
          key="submit"
          type="default"
          onClick={() => {
            mutation.mutate(metric.metric_id);
          }}
          disabled={(import.meta as any).env.VITE_IS_DEMO === "true"}
        >
          Archive
        </Button>,
        <Button
          key="save-display"
          type="primary"
          onClick={() => displayMutation.mutate(displayState)}
        >
          Save Pricing Page Display
        </Button>,
        <Button key="close" type="default" onClick={onclose}>
          Close
        </Button>,
      ]}
      cancelText="Close"
      width={800}
      onCancel={onclose}
    >
      <div className="py-4 px-8 rounded-lg bg-[#FFFFFF]  border-2 border-solid  border-[#EAEAEB]">
        {metric.metric_type === "custom" ? (
          <div className="flex flex-col">
            <p>
              <b className="mr-2">Metric ID:</b>{" "}
              <div className="flex gap-1 text-card-grey font-menlo">
                {" "}
                <div>
                  {createShortenedText(metric.metric_id, windowWidth >= 2500)}
                </div>
                <CopyText showIcon onlyIcon textToCopy={metric.metric_id} />
              </div>
            </p>
            <b>Query:</b>
            <p className="text-sm text-gray-800 font-mono whitespace-pre">
              {" "}
              {formattedSQL}
            </p>
          </div>
        ) : (
          <div className="py-4 grid grid-cols-2 items-start justify-between ">
            <p>
              <b className="mr-2">Metric ID:</b>{" "}
              <div className="flex gap-1 text-card-grey font-menlo">
                {" "}
                <div>
                  {createShortenedText(metric.metric_id, windowWidth >= 2500)}
                </div>
                <CopyText showIcon onlyIcon textToCopy={metric.metric_id} />
              </div>
            </p>
            <p>
              <b className="mr-2">Event Name:</b> {metric.event_name}
            </p>
            <p>
              <b className="mr-2">Cost Metric:</b>{" "}
              {metric.is_cost_metric ? "Yes" : "No"}
            </p>
            <p>
              <b className="mr-2">Property Name:</b>{" "}
              {metric.property_name ?? "N/A"}
            </p>
            <p>
              <b className="mr-2">Metric Type:</b>
              {metric.metric_type === "gauge" ? "gauge" : metric.metric_type}
            </p>
            <p>
              <b className="mr-2">Per Time Unit:</b>{" "}
              {metric.granularity === "total" ? "-" : metric.granularity}
            </p>
            <p>
              <b className="mr-2">Proration:</b>{" "}
              {metric.proration === "total" || metric.proration == undefined
                ? "none"
                : metric.proration}
            </p>
            <p>
              <b className="mr-2">Usage Aggregation Type:</b>
              <Tag color={colorMap.get(metric.usage_aggregation_type)}>
                {metric.usage_aggregation_type}
              </Tag>
            </p>
            {/* {metric.metric_type === "rate" && (
              <p>
                <b className="mr-2">Aggregation Type:</b>
                {metric.billable_aggregation_type ? (
                  <Tag>{metric.billable_aggregation_type}</Tag>
                ) : (
                  "N/A"
                )}
              </p>
            )} */}
            {metric.metric_type === "gauge" && (
              <p>
                <b className="mr-2">Event Type:</b>
                {metric.event_type ? <Tag>{metric.event_type}</Tag> : "N/A"}
              </p>
            )}

            <p>
              <b className="mr-2">Filters:</b>
            </p>
            <div className="grid col-span-2">
              <div>
                {metric.numeric_filters?.map((filter, index) => (
                  <Tag color="" key={filter.property_name}>
                    <b>{filter.property_name}</b>{" "}
                    {operatorDisplayMap.get(filter.operator)}{" "}
                    {`${filter.comparison_value}`}
                  </Tag>
                ))}
              </div>

              <div>
                {metric.categorical_filters?.map((filter, index) => (
                  <Tag color="" key={filter.property_name}>
                    {<b>{filter.property_name}</b>}{" "}
                    {operatorDisplayMap.get(filter.operator)}{" "}
                    {Array.isArray(filter.comparison_value)
                      ? `[${filter.comparison_value
                          .map((value) => `"${value}"`)
                          .join(", ")}]`
                      : `${filter.comparison_value}`}
                  </Tag>
                ))}
              </div>
            </div>
          </div>
        )}
        <div className="mt-6 pt-4 border-t border-solid border-[#EAEAEB]">
          <b>Pricing page display</b>
          <div className="grid grid-cols-2 gap-4 mt-2">
            <div>
              <label className="block mb-1">Display name</label>
              <Input
                placeholder={metric.metric_name}
                value={displayState.display_name ?? ""}
                onChange={(e) =>
                  setDisplayState({
                    ...displayState,
                    display_name: e.target.value,
                  })
                }
              />
            </div>
            <div>
              <label className="block mb-1">Format</label>
              <Select
                style={{ width: "100%" }}
                allowClear
                placeholder="None"
                value={displayState.display_format ?? undefined}
                onChange={(value) =>
                  setDisplayState({
                    ...displayState,
                    display_format: value ?? null,
                  })
                }
                options={MetricDisplayFormats.map((displayFormat) => ({
                  label:
                    displayFormat === "percentage"
                      ? "Percentage"
                      : "Per unit",
                  value: displayFormat,
                }))}
              />
            </div>
            <div>
              <label className="block mb-1">Unit</label>
              <Input
                placeholder='e.g. "sales" or "SMS"'
                value={displayState.display_unit ?? ""}
                onChange={(e) =>
                  setDisplayState({
                    ...displayState,
                    display_unit: e.target.value,
                  })
                }
              />
            </div>
            <div>
              <label className="block mb-1">Section</label>
              <Select
                style={{ width: "100%" }}
                allowClear
                placeholder="None"
                value={displayState.display_section_id ?? undefined}
                onChange={(value) =>
                  setDisplayState({
                    ...displayState,
                    display_section_id: value ?? null,
                  })
                }
                options={(sections ?? []).map((section) => ({
                  label: section.name,
                  value: section.section_id,
                }))}
              />
            </div>
            <div className="col-span-2">
              <label className="block mb-1">Description</label>
              <Input.TextArea
                value={displayState.display_description ?? ""}
                onChange={(e) =>
                  setDisplayState({
                    ...displayState,
                    display_description: e.target.value,
                  })
                }
              />
            </div>
            <div>
              <label className="block mb-1">Order within section</label>
              <InputNumber
                style={{ width: "100%" }}
                value={displayState.display_order}
                onChange={(value) =>
                  setDisplayState({
                    ...displayState,
                    display_order: value ?? 0,
                  })
                }
              />
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
};

export default MetricDetails;
