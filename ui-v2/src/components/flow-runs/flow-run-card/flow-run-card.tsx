import { cva } from "class-variance-authority";
import type { Deployment } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
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
	return (
		<Card className={stateCardVariants({ state: flowRun.state?.type })}>
			{/** First Row */}
			<div className="flex justify-between items-center">
				<div className="flex items-center gap-2">
					{"checked" in props && "onCheckedChange" in props && (
						<Checkbox
							checked={props.checked}
							onCheckedChange={props.onCheckedChange}
						/>
					)}
					<FlowRunName flowRun={flowRun} />
				</div>
				<div>
					<TagBadgeGroup tags={flowRun.tags} />
				</div>
			</div>
			{/** Second Row */}
			<div className="flex items-center gap-2">
				{flowRun.state && (
					<StateBadge type={flowRun.state.type} name={flowRun.state.name} />
				)}
				<FlowRunStartTime flowRun={flowRun} />
				<FlowRunParameters flowRun={flowRun} />
				{flowRun.state?.type !== "SCHEDULED" && (
					<>
						<FlowRunDuration flowRun={flowRun} />
						<FlowRunTaskRuns flowRun={flowRun} />
					</>
				)}
			</div>
			{/** Third Row Row */}
			<div className="flex items-center gap-2">
				{flowRun.deployment && (
					<FlowRunDeployment deployment={flowRun.deployment} />
				)}
			</div>
		</Card>
	);
};

const stateCardVariants = cva("flex flex-col gap-2 p-4 border-l-8", {
	variants: {
		state: {
			COMPLETED: "border-l-green-600",
			FAILED: "border-l-red-600",
			RUNNING: "border-l-blue-700",
			CANCELLED: "border-l-gray-800",
			CANCELLING: "border-l-gray-800",
			CRASHED: "border-l-orange-600",
			PAUSED: "border-l-gray-800",
			PENDING: "border-l-gray-800",
			SCHEDULED: "border-l-yellow-700",
		} satisfies Record<components["schemas"]["StateType"], string>,
	},
});
