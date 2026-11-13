import React, { FC } from "react";
import { Button, Tooltip } from "antd";
import { StarFilled, StarOutlined } from "@ant-design/icons";

interface HighlightStarProps {
  // Position in the version's highlight list, or -1 when not highlighted.
  highlightIndex: number;
  canToggle: boolean;
  pending: boolean;
  onToggle: () => void;
}

const HighlightStar: FC<HighlightStarProps> = ({
  highlightIndex,
  canToggle,
  pending,
  onToggle,
}) => {
  const isHighlighted = highlightIndex !== -1;
  if (!canToggle && !isHighlighted) {
    return null;
  }
  return (
    <Tooltip
      title={
        isHighlighted
          ? `Highlight #${highlightIndex + 1} on the pricing page${
              canToggle ? " — click to remove" : ""
            }`
          : "Highlight on the pricing page"
      }
    >
      <Button
        type="text"
        size="small"
        aria-label={isHighlighted ? "Remove highlight" : "Mark as highlight"}
        disabled={!canToggle || pending}
        onClick={onToggle}
        className="!flex items-center gap-1 !px-1"
      >
        {isHighlighted ? (
          <>
            <StarFilled style={{ color: "#C3986B" }} />
            <span className="text-xs text-gold">{highlightIndex + 1}</span>
          </>
        ) : (
          <StarOutlined className="text-card-grey" />
        )}
      </Button>
    </Tooltip>
  );
};

export default HighlightStar;
