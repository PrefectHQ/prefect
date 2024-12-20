import { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { Typography } from "@/components/ui/typography";
import { secondsToApproximateString } from "@/utilities/seconds";
import { Link } from "@tanstack/react-router";
import { cva } from "class-variance-authority";
import { format, parseISO } from "date-fns";

type Props = {
	flow: components["schemas"]["Flow"];
	flowRun: components["schemas"]["FlowRun"];
	taskRun: components["schemas"]["TaskRun"];
};

export const ConcurrencyLimitTaskRunCard = ({
	flow,
	flowRun,
	taskRun,
}: Props) => {
	return (
		<Card className={stateCardVariants({ state: taskRun.state?.type })}>
			<div className="flex justify-between items-center">
				<ConcurrencyLimitTaskRunBreadcrumb
					flow={flow}
					flowRun={flowRun}
					taskRun={taskRun}
				/>
				<div>
					<TagBadgeGroup maxTagsDisplayed={5} tags={taskRun.tags} />
				</div>
			</div>
			<div className="flex gap-2 items-center text-slate-600">
				{taskRun.state && <StateBadge state={taskRun.state} />}
				<TimeRan duration={taskRun.estimated_run_time} />
				{taskRun.start_time && <StartTime time={taskRun.start_time} />}
			</div>
		</Card>
	);
};

const ConcurrencyLimitTaskRunBreadcrumb = ({
	flow,
	flowRun,
	taskRun,
}: Props) => {
	if (!flow.id || !flowRun.id || !taskRun.id) {
		throw new Error("'id' field expected");
	}

	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<Link to="/flows/flow/$id" params={{ id: flow.id }}>
						{flow.name}
					</Link>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem>
					<Link to="/runs/flow-run/$id" params={{ id: flow.id }}>
						{flowRun.name}
					</Link>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem>
					<Link to="/runs/task-run/$id" params={{ id: taskRun.id }}>
						{taskRun.name}
					</Link>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};

type TimeRanProps = {
	duration: number;
};
const TimeRan = ({ duration }: TimeRanProps) => {
	return (
		<div className="flex gap-1 items-center">
			<Icon id="Clock" className="h-4 w-4" />
			<Typography variant="bodySmall">
				{secondsToApproximateString(duration)}
			</Typography>
		</div>
	);
};

type StartTimeProps = {
	time: string;
};
const StartTime = ({ time }: StartTimeProps) => (
	<Typography variant="bodySmall">
		{format(parseISO(time), "yyyy/MM/dd pp")}
	</Typography>
);

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
