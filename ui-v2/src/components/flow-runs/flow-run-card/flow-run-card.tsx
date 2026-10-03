import { cva } from "class-variance-authority";
import { Suspense } from "react";
import type { Deployment } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import { isTerminalState } from "@/api/flow-runs/state-utilities";
import type { Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { WorkPoolLink } from "@/components/work-pools/work-pool-link";
import { WorkQueueIconText } from "@/components/work-pools/work-queue-icon-text";
import { FlowRunDeployment } from "./card-properties/flow-run-deployment";
import { FlowRunDuration } from "./card-properties/flow-run-duration";
import { FlowRunName } from "./card-properties/flow-run-name";
import { FlowRunParameters } from "./card-properties/flow-run-parameters";
import { FlowRunStartTime } from "./card-properties/flow-run-start-time";
import { FlowRunTaskRuns } from "./card-properties/flow-run-task-runs";

export type FlowRunCardData = FlowRun & {
	flow?: Flow;
	deployment?: Deployment;
};

type FlowRunCardProps =
	| {
			flowRun: FlowRunCardData;
	  }
	| {
			flowRun: FlowRunCardData;
			checked: boolean;
			onCheckedChange: (checked: boolean) => void;
	  };

export const FlowRunCard = ({ flowRun, ...props }: FlowRunCardProps) => {
	const hasRelationships = Boolean(
		flowRun.deployment || flowRun.work_pool_name,
	);

	return (
		<Card className={stateCardVariants({ state: flowRun.state?.type })}>
			{/** First Row */}
			<div className="flex justify-between items-center min-w-0 overflow-hidden">
				<div className="flex items-center gap-2 min-w-0">
					{"checked" in props && "onCheckedChange" in props && (
						<Checkbox
							checked={props.checked}
							onCheckedChange={props.onCheckedChange}
						/>
					)}
					<FlowRunName flowRun={flowRun} />
				</div>
				<div className="flex-1 min-w-12 flex justify-end">
					<TagBadgeGroup tags={flowRun.tags} />
				</div>
			</div>
			{/** Second Row */}
			<div className="flex flex-wrap items-center gap-x-2 gap-y-1">
				{flowRun.state && (
					<StateBadge type={flowRun.state.type} name={flowRun.state.name} />
				)}
				<FlowRunStartTime flowRun={flowRun} />
				<FlowRunParameters flowRun={flowRun} />
				{flowRun.state?.type !== "SCHEDULED" && (
					<>
						<FlowRunDuration flowRun={flowRun} />
						<Suspense>
							<FlowRunTaskRuns flowRun={flowRun} />
						</Suspense>
					</>
				)}
			</div>
			{/** Third Row */}
			{hasRelationships && (
				<div className="flex flex-wrap items-center gap-x-4 gap-y-1">
					{flowRun.deployment && (
						<FlowRunDeployment deployment={flowRun.deployment} />
					)}
					{flowRun.work_pool_name && (
						<WorkPoolLink workPoolName={flowRun.work_pool_name} />
					)}
					{flowRun.work_pool_name && flowRun.work_queue_name && (
						<WorkQueueIconText
							workPoolName={flowRun.work_pool_name}
							workQueueName={flowRun.work_queue_name}
							showLabel
							showStatus={!isTerminalState(flowRun.state?.type)}
						/>
					)}
				</div>
			)}
		</Card>
	);
};

const stateCardVariants = cva("flex flex-col gap-2 p-4 border-l-8", {
	variants: {
		state: {
			COMPLETED: "border-l-state-completed-600",
			FAILED: "border-l-state-failed-600",
			RUNNING: "border-l-state-running-600",
			CANCELLED: "border-l-state-cancelled-600",
			CANCELLING: "border-l-state-cancelling-600",
			CRASHED: "border-l-state-crashed-600",
			PAUSED: "border-l-state-paused-600",
			PENDING: "border-l-state-pending-600",
			SCHEDULED: "border-l-state-scheduled-600",
		} satisfies Record<components["schemas"]["StateType"], string>,
	},
});
