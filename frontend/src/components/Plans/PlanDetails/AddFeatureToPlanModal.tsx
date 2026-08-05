/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable camelcase */
import React, { useEffect, useMemo, useState } from "react";
import { Alert, Button, Checkbox, Modal, Radio, Select, Tag } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { Features, Plan } from "../../../api/api";
import { components } from "../../../gen-types";
import { FeatureType } from "../../../types/feature-type";

type PlanVersionDetail = components["schemas"]["PlanVersionDetail"];
type PlanVersions = components["schemas"]["PlanDetail"]["versions"];

type Scope = "this" | "specific" | "all";

// Exactly one of these keys may be sent. Sending neither resolves server-side to
// an empty queryset and returns a misleading 200 "added to 0 versions"; the
// serializer's own "can't send both" guard is dead code, so the client is the
// only thing enforcing this.
type ScopePayload = { all_versions: true } | { version_ids: string[] };

interface AddFeatureToPlanModalProps {
  showModal: boolean;
  setShowModal: (show: boolean) => void;
  plan_id: string;
  versions: PlanVersions;
  selectedVersion: PlanVersionDetail;
}

const versionNumberLabel = (version: PlanVersionDetail) =>
  typeof version.version === "number"
    ? `v${version.version}`
    : version.localized_name || "Custom";

const versionLabel = (version: PlanVersionDetail) => {
  const code = version.currency?.code;
  return code
    ? `${versionNumberLabel(version)} — ${code}`
    : versionNumberLabel(version);
};

const statusBreakdown = (versions: PlanVersionDetail[]) => {
  const counts: Record<string, number> = {};
  versions.forEach((v) => {
    counts[v.status] = (counts[v.status] ?? 0) + 1;
  });
  return Object.entries(counts)
    .map(([status, count]) => `${count} ${status}`)
    .join(", ");
};

const hasFeature = (version: PlanVersionDetail, feature_id: string) =>
  version.features.some((f) => f.feature_id === feature_id);

const AddFeatureToPlanModal = ({
  showModal,
  setShowModal,
  plan_id,
  versions,
  selectedVersion,
}: AddFeatureToPlanModalProps) => {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<Scope>("this");
  const [versionIds, setVersionIds] = useState<string[]>([]);
  const [featureIds, setFeatureIds] = useState<string[]>([]);

  const { data: features, isLoading: featuresLoading } = useQuery<FeatureType[]>(
    ["feature_list"],
    () => Features.getFeatures(),
    { enabled: showModal },
  );

  // "all_versions" server-side means plan.versions, which includes custom
  // versions the Versions tab never shows (it fetches public_only). Fetch the
  // full list so the counts and the "already added" state tell the truth.
  const { data: allVersionsPlan } = useQuery(
    ["plan_detail_all_versions", plan_id],
    () => Plan.getPlan(plan_id, "all"),
    { enabled: showModal },
  );

  const authoritativeVersions: PlanVersionDetail[] = useMemo(
    () => [...((allVersionsPlan?.versions ?? versions) as PlanVersionDetail[])],
    [allVersionsPlan, versions],
  );

  // The version pills collapse currency siblings into one chip, so "this
  // version" means every row sharing that version number, not just the
  // currently displayed currency.
  const currencySiblings = useMemo(
    () =>
      authoritativeVersions.filter((v) => v.version === selectedVersion.version),
    [authoritativeVersions, selectedVersion],
  );

  const targetVersions: PlanVersionDetail[] = useMemo(() => {
    if (scope === "all") return authoritativeVersions;
    if (scope === "specific")
      return authoritativeVersions.filter((v) =>
        versionIds.includes(v.version_id),
      );
    return currencySiblings;
  }, [scope, versionIds, authoritativeVersions, currencySiblings]);

  const isFullyCovered = (feature_id: string) =>
    targetVersions.length > 0 &&
    targetVersions.every((v) => hasFeature(v, feature_id));

  const featureOptions = useMemo(
    () =>
      (features ?? []).map((feature) => {
        const covered = targetVersions.filter((v) =>
          hasFeature(v, feature.feature_id),
        ).length;
        const fullyCovered =
          targetVersions.length > 0 && covered === targetVersions.length;
        let suffix = "";
        if (fullyCovered) {
          suffix = " (already added)";
        } else if (covered > 0) {
          suffix = ` (on ${covered} of ${targetVersions.length})`;
        }
        return {
          value: feature.feature_id,
          label: `${feature.feature_name}${suffix}`,
          disabled: fullyCovered,
        };
      }),
    [features, targetVersions],
  );

  useEffect(() => {
    if (showModal) {
      setScope("this");
      setVersionIds([]);
      setFeatureIds([]);
    }
  }, [showModal]);

  // A feature that becomes fully covered after a scope change would submit as a
  // silent no-op, so drop it from the selection.
  useEffect(() => {
    setFeatureIds((prev) => prev.filter((id) => !isFullyCovered(id)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, versionIds, allVersionsPlan]);

  const scopePayload = (): ScopePayload =>
    scope === "all"
      ? { all_versions: true }
      : { version_ids: targetVersions.map((v) => v.version_id) };

  const mutation = useMutation(
    async () => {
      const payload = scopePayload();
      const succeeded: string[] = [];
      const failed: { feature_id: string; message: string }[] = [];

      // One feature_id per request, so fan out sequentially and account for
      // each: a partial write cannot be undone (there is no detach endpoint).
      // eslint-disable-next-line no-restricted-syntax
      for (const feature_id of featureIds) {
        try {
          // eslint-disable-next-line no-await-in-loop
          await Plan.featuresAddPlan(plan_id, { feature_id, ...payload });
          succeeded.push(feature_id);
        } catch (err) {
          const message =
            (err as any)?.response?.data?.detail ??
            (err as Error)?.message ??
            "Unknown error";
          failed.push({ feature_id, message });
        }
      }
      return { succeeded, failed };
    },
    {
      onSuccess: ({ succeeded, failed }) => {
        const nameOf = (id: string) =>
          features?.find((f) => f.feature_id === id)?.feature_name ?? id;

        if (succeeded.length > 0) {
          queryClient.invalidateQueries(["plan_list"]);
          queryClient.invalidateQueries(["plan_detail", plan_id]);
          queryClient.invalidateQueries(["plan_detail_all_versions", plan_id]);
        }

        const versionCount =
          scope === "all" ? authoritativeVersions.length : targetVersions.length;

        if (failed.length === 0) {
          toast.success(
            succeeded.length === 1
              ? `Added "${nameOf(succeeded[0])}" to ${versionCount} version(s)`
              : `Added ${succeeded.length} features to ${versionCount} version(s)`,
          );
          setShowModal(false);
          return;
        }

        // Keep the modal open with only the failures selected. Re-submitting is
        // safe: the backend uses m2m .add(), which is idempotent.
        setFeatureIds(failed.map((f) => f.feature_id));
        const failedNames = failed.map((f) => nameOf(f.feature_id)).join(", ");
        if (succeeded.length === 0) {
          toast.error(`Could not add: ${failedNames}. ${failed[0].message}`);
        } else {
          toast.error(
            `Added ${succeeded.length} of ${
              succeeded.length + failed.length
            } features. Failed: ${failedNames}`,
          );
        }
      },
      onError: () => {
        toast.error("Could not add features to this plan");
      },
    },
  );

  const submittable =
    featureIds.length > 0 &&
    !mutation.isLoading &&
    (scope === "all" || targetVersions.length > 0);

  const singleVersionPlan = authoritativeVersions.length <= 1;
  const siblingCurrencies = currencySiblings
    .map((v) => v.currency?.code)
    .filter(Boolean)
    .join(", ");

  return (
    <Modal
      title="Add Feature"
      visible={showModal}
      onCancel={() => setShowModal(false)}
      footer={[
        <Button
          key="back"
          onClick={() => setShowModal(false)}
          style={{ background: "#F5F5F5", borderColor: "#F5F5F5" }}
        >
          Cancel
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={mutation.isLoading}
          onClick={() => mutation.mutate()}
          disabled={!submittable}
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          Add Feature
        </Button>,
      ]}
    >
      <div className="flex flex-col gap-4">
        <Alert
          type="warning"
          showIcon
          message="Features can't be removed from a version once added, and existing subscribers get access immediately."
        />

        <div className="flex flex-col gap-2">
          <label className="required">Features</label>
          <Select
            mode="multiple"
            allowClear
            className="w-full"
            placeholder="Select features"
            loading={featuresLoading}
            value={featureIds}
            onChange={setFeatureIds}
            options={featureOptions}
            optionFilterProp="label"
            notFoundContent={
              features && features.length === 0
                ? "No features exist yet — create one on the Features page"
                : undefined
            }
          />
        </div>

        {singleVersionPlan ? (
          <div className="text-card-grey">
            {`This plan has one version (${versionLabel(
              selectedVersion,
            )}) — the feature will be added to it.`}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <label className="required">Apply to</label>
            <Radio.Group
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
            >
              <div className="flex flex-col gap-2">
                <Radio value="this">
                  {`This version only (${versionNumberLabel(selectedVersion)}${
                    siblingCurrencies ? ` — ${siblingCurrencies}` : ""
                  })`}
                </Radio>
                <Radio value="all">
                  {`All versions (${
                    authoritativeVersions.length
                  }: ${statusBreakdown(authoritativeVersions)})`}
                </Radio>
                <Radio value="specific">Select versions…</Radio>
              </div>
            </Radio.Group>

            {scope === "all" && (
              <div className="text-card-grey text-sm">
                Includes inactive and grandfathered versions, and any custom
                versions of this plan.
              </div>
            )}

            {scope === "specific" && (
              <Checkbox.Group
                value={versionIds}
                onChange={(checked) => setVersionIds(checked as string[])}
              >
                <div className="flex flex-col gap-2 max-h-40 overflow-y-auto">
                  {authoritativeVersions.map((v) => (
                    <Checkbox key={v.version_id} value={v.version_id}>
                      <span className="flex gap-2 items-center">
                        {versionLabel(v)}
                        <Tag>{v.status}</Tag>
                      </span>
                    </Checkbox>
                  ))}
                </div>
              </Checkbox.Group>
            )}
          </div>
        )}

        {featureIds.length > 0 && (
          <div className="text-card-grey">
            {`Will add ${featureIds.length} feature(s) to ${
              scope === "all"
                ? authoritativeVersions.length
                : targetVersions.length
            } version(s).`}
          </div>
        )}
      </div>
    </Modal>
  );
};

export default AddFeatureToPlanModal;
