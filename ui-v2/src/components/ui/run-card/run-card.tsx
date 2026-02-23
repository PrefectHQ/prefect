import { cva } from "class-variance-authority";
import { format, parseISO } from "date-fns";
import humanizeDuration from "humanize-duration";
import type { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";

const getValues = ({
	flowRun,
	taskRun,
}: {
	flowRun: null | undefined | components["schemas"]["FlowRunResponse"];
	taskRun: null | undefined | components["schemas"]["TaskRun"];
}) => {
	if (taskRun) {
		const { state, start_time, tags, estimated_run_time } = taskRun;
		return { state, start_time, tags, estimated_run_time };
	}
	if (flowRun) {
		const { state, start_time, tags, estimated_run_time } = flowRun;
		return { state, start_time, tags, estimated_run_time };
	}

	throw new Error("Expecting taskRun or flowRun to be defined");
};

type RunCardProps = {
	flow?: components["schemas"]["Flow"] | null;
	flowRun?: components["schemas"]["FlowRunResponse"] | null;
	/** If task run is included, uses fields from task run over flow run */
	taskRun?: components["schemas"]["TaskRun"] | null;
};

export const RunCard = ({ flow, flowRun, taskRun }: RunCardProps) => {
	const { state, start_time, tags, estimated_run_time } = getValues({
		flowRun,
		taskRun,
	});

	return (
		<Card className={stateCardVariants({ state: state?.type })}>
			<div className="flex justify-between items-center">
				<ConcurrencyLimitTaskRunBreadcrumb
					flow={flow}
					flowRun={flowRun}
					taskRun={taskRun}
				/>
				<div>
					<TagBadgeGroup maxTagsDisplayed={5} tags={tags} />
				</div>
			</div>
			<div className="flex gap-2 items-center text-muted-foreground">
				{state && <StateBadge type={state.type} name={state.name} />}
				{start_time && <StartTime time={start_time} />}
				<TimeRan duration={estimated_run_time} />
			</div>
		</Card>
	);
};

const ConcurrencyLimitTaskRunBreadcrumb = ({
	flow,
	flowRun,
	taskRun,
}: RunCardProps) => {
	if (!flow && !flowRun && !taskRun) {
		throw new Error("Expecting flow, flowRun, or taskRun");
	}

	return (
		<Breadcrumb>
			<BreadcrumbList>
				{flow && (
					<BreadcrumbItem>
						<BreadcrumbLink
							className="text-lg font-semibold"
							to="/flows/flow/$id"
							params={{ id: flow.id }}
						>
							{flow.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				)}
				{flow && flowRun && <BreadcrumbSeparator />}
				{flowRun && (
					<BreadcrumbItem>
						<BreadcrumbLink to="/runs/flow-run/$id" params={{ id: flowRun.id }}>
							{flowRun.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				)}
				{flowRun && taskRun && <BreadcrumbSeparator />}
				{taskRun && (
					<BreadcrumbItem>
						<BreadcrumbLink to="/runs/task-run/$id" params={{ id: taskRun.id }}>
							{taskRun.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				)}
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
			<Icon id="Clock" className="size-4" />
			<p className="text-sm">
				{humanizeDuration(duration, { maxDecimalPoints: 3, units: ["s"] })}
			</p>
		</div>
	);
};

type StartTimeProps = {
	time: string;
};
const StartTime = ({ time }: StartTimeProps) => (
	<div className="flex gap-1 items-center">
		<Icon id="Calendar" className="size-4" />
		<p className="text-sm font-mono">
			{format(parseISO(time), "yyyy/MM/dd pp")}
		</p>
	</div>
);

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
