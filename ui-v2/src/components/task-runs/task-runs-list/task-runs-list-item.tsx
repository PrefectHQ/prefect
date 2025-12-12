import { useSuspenseQuery } from "@tanstack/react-query";
import { cva } from "class-variance-authority";
import humanizeDuration from "humanize-duration";
import { Suspense, useMemo } from "react";
import { buildGetFlowRunDetailsQuery, type FlowRun } from "@/api/flow-runs";
import { buildFLowDetailsQuery, type Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import type { TaskRun, TaskRunResponse } from "@/api/task-runs";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDate } from "@/utils/date";

type TaskRunsListItemProps = {
	taskRun: TaskRun | TaskRunResponse;
	flow?: Flow;
	flowRun?: FlowRun;
	checked?: boolean;
	onCheckedChange?: (checked: boolean) => void;
};

export const TaskRunsListItem = ({
	taskRun,
	flow,
	flowRun,
	checked,
	onCheckedChange,
}: TaskRunsListItemProps) => {
	const isSelectable = typeof onCheckedChange === "function";

	return (
		<Card className={stateCardVariants({ state: taskRun.state?.type })}>
			<div className="flex justify-between items-center">
				<div className="flex items-center gap-2">
					{isSelectable && (
						<Checkbox
							checked={checked ?? false}
							onCheckedChange={onCheckedChange}
						/>
					)}
					<TaskRunBreadcrumbs taskRun={taskRun} flow={flow} flowRun={flowRun} />
				</div>
				<div>
					<TagBadgeGroup tags={taskRun.tags ?? []} />
				</div>
			</div>
			<div className="flex items-center gap-2">
				{taskRun.state && (
					<StateBadge type={taskRun.state.type} name={taskRun.state.name} />
				)}
				<TaskRunStartTime taskRun={taskRun} />
				<TaskRunDuration taskRun={taskRun} />
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

type TaskRunBreadcrumbsProps = {
	taskRun: TaskRun | TaskRunResponse;
	flow?: Flow;
	flowRun?: FlowRun;
};

const TaskRunBreadcrumbs = ({
	taskRun,
	flow,
	flowRun,
}: TaskRunBreadcrumbsProps) => {
	return (
		<div className="flex items-center">
			<Breadcrumb>
				<BreadcrumbList>
					{flow && (
						<>
							<BreadcrumbItem>
								<BreadcrumbLink
									to="/flows/flow/$id"
									params={{ id: flow.id }}
									className="font-semibold text-foreground"
								>
									{flow.name}
								</BreadcrumbLink>
							</BreadcrumbItem>
							<BreadcrumbSeparator />
						</>
					)}
					{flowRun && (
						<>
							<BreadcrumbItem>
								<BreadcrumbLink
									to="/runs/flow-run/$id"
									params={{ id: flowRun.id }}
								>
									{flowRun.name}
								</BreadcrumbLink>
							</BreadcrumbItem>
							<BreadcrumbSeparator />
						</>
					)}
					<BreadcrumbItem className="font-bold text-foreground">
						<BreadcrumbLink to="/runs/task-run/$id" params={{ id: taskRun.id }}>
							{taskRun.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
};

type TaskRunStartTimeProps = {
	taskRun: TaskRun | TaskRunResponse;
};

const TaskRunStartTime = ({ taskRun }: TaskRunStartTimeProps) => {
	// These properties only exist on UITaskRun, not TaskRunResponse
	const start_time =
		"start_time" in taskRun ? (taskRun.start_time as string | null) : null;
	const expected_start_time =
		"expected_start_time" in taskRun
			? (taskRun.expected_start_time as string | null)
			: null;

	const { text, tooltipText } = useMemo(() => {
		let text: string | undefined;
		let tooltipText: string | undefined;
		if (start_time) {
			text = formatDate(start_time, "dateTimeNumeric");
			tooltipText = new Date(start_time).toString();
		} else if (expected_start_time) {
			text = `Scheduled for ${formatDate(expected_start_time, "dateTimeNumeric")}`;
			tooltipText = new Date(expected_start_time).toString();
		}
		return { text, tooltipText };
	}, [expected_start_time, start_time]);

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild disabled={!text}>
					<div className="text-xs font-mono flex gap-2 items-center">
						<Icon id="Calendar" className="size-4" />
						{text ?? "No start time"}
					</div>
				</TooltipTrigger>
				<TooltipContent>{tooltipText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

type TaskRunDurationProps = {
	taskRun: TaskRun | TaskRunResponse;
};

const TaskRunDuration = ({ taskRun }: TaskRunDurationProps) => {
	// These properties only exist on UITaskRun, not TaskRunResponse
	const estimated_run_time =
		"estimated_run_time" in taskRun
			? (taskRun.estimated_run_time as number | null)
			: null;
	const total_run_time =
		"total_run_time" in taskRun
			? (taskRun.total_run_time as number | null)
			: null;
	const duration = estimated_run_time ?? total_run_time ?? 0;

	if (duration === 0) {
		return null;
	}

	const durationLabel = humanizeDuration(duration * 1000, {
		maxDecimalPoints: 2,
		units: ["h", "m", "s"],
		round: true,
	});
	const durationTooltip = humanizeDuration(duration * 1000, {
		maxDecimalPoints: 5,
		units: ["h", "m", "s"],
	});

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<div className="flex gap-2 items-center text-xs font-mono">
						<Icon id="Clock" className="size-4" />
						{durationLabel}
					</div>
				</TooltipTrigger>
				<TooltipContent>{durationTooltip}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

type TaskRunsListItemWithDataProps = {
	taskRun: TaskRun | TaskRunResponse;
	checked?: boolean;
	onCheckedChange?: (checked: boolean) => void;
};

type TaskRunsListItemWithFlowDataProps = {
	taskRun: TaskRun | TaskRunResponse;
	flowRunId: string;
	checked?: boolean;
	onCheckedChange?: (checked: boolean) => void;
};

const TaskRunsListItemWithFlowData = ({
	taskRun,
	flowRunId,
	checked,
	onCheckedChange,
}: TaskRunsListItemWithFlowDataProps) => {
	const { data: flowRun } = useSuspenseQuery(
		buildGetFlowRunDetailsQuery(flowRunId),
	);
	const { data: flow } = useSuspenseQuery(
		buildFLowDetailsQuery(flowRun.flow_id),
	);

	return (
		<TaskRunsListItem
			taskRun={taskRun}
			flow={flow}
			flowRun={flowRun}
			checked={checked}
			onCheckedChange={onCheckedChange}
		/>
	);
};

const TaskRunsListItemWithDataInner = ({
	taskRun,
	checked,
	onCheckedChange,
}: TaskRunsListItemWithDataProps) => {
	const flowRunId = taskRun.flow_run_id;

	if (!flowRunId) {
		return (
			<TaskRunsListItem
				taskRun={taskRun}
				checked={checked}
				onCheckedChange={onCheckedChange}
			/>
		);
	}

	return (
		<TaskRunsListItemWithFlowData
			taskRun={taskRun}
			flowRunId={flowRunId}
			checked={checked}
			onCheckedChange={onCheckedChange}
		/>
	);
};

export const TaskRunsListItemWithData = ({
	taskRun,
	checked,
	onCheckedChange,
}: TaskRunsListItemWithDataProps) => {
	return (
		<Suspense
			fallback={
				<Card className="flex flex-col gap-2 p-4 border-l-8 border-l-gray-300 animate-pulse">
					<div className="h-5 bg-gray-200 rounded w-1/3" />
					<div className="h-4 bg-gray-200 rounded w-1/4" />
				</Card>
			}
		>
			<TaskRunsListItemWithDataInner
				taskRun={taskRun}
				checked={checked}
				onCheckedChange={onCheckedChange}
			/>
		</Suspense>
	);
};
