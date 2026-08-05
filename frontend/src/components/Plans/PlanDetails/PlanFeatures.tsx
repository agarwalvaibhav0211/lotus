import React, { FC } from "react";
import "./PlanDetails.css";
import { Button, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { FeatureType } from "../../../types/feature-type";
import CopyText from "../../base/CopytoClipboard";
import createShortenedText from "../../../helpers/createShortenedText";
import useMediaQuery from "../../../hooks/useWindowQuery";

interface PlanFeaturesProps {
  features?: FeatureType[];
  // When omitted, the card stays read-only (add-ons and custom plans).
  onAddFeature?: () => void;
}

const PlanFeatures: FC<PlanFeaturesProps> = ({ features, onAddFeature }) => {
  const windowWidth = useMediaQuery();
  const canAddFeature =
    !!onAddFeature && !((import.meta as any).env.VITE_IS_DEMO === "true");

  const addFeatureButton = (
    <Button
      key="add-feature"
      htmlType="button"
      type="primary"
      onClick={onAddFeature}
      id="add-feature-to-plan-button"
      className="hover:!bg-primary-700"
      style={{ background: "#C3986B", borderColor: "#C3986B" }}
    >
      <div className="flex items-center justify-between text-white">
        <div>
          <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
          Add Feature
        </div>
      </div>
    </Button>
  );

  return (
    <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card ">
      <div className="flex items-center justify-between">
        <Typography.Title className="!text-[18px] !mb-0">
          Features
        </Typography.Title>
        {canAddFeature && addFeatureButton}
      </div>
      <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
      <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
        {features && features.length > 0 ? (
          features.map((feature) => (
            <div
              key={feature.feature_id}
              className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px]"
            >
              <div className="text-base text-card-text">
                <div>{feature.feature_name}</div>
                <div className="flex gap-1 text-card-grey font-menlo">
                  {" "}
                  <div>
                    {createShortenedText(
                      feature.feature_id,
                      windowWidth >= 2500,
                    )}
                  </div>
                  <CopyText showIcon onlyIcon textToCopy={feature.feature_id} />
                </div>
              </div>
              <div />
              <div className="text-card-grey">
                {feature.feature_description}
              </div>
            </div>
          ))
        ) : (
          <div className="text-card-grey">No features added</div>
        )}
      </div>
    </div>
  );
};
export default PlanFeatures;
