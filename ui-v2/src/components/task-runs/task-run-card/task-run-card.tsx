import { Link } from "@tanstack/react-router";
import { cva } from "class-variance-authority";
import humanizeDuration from "humanize-duration";
import type { components } from "@/api/prefect";
import type { TaskRun } from "@/api/task-runs";
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

export type TaskRunCardData = TaskRun;

type TaskRunCardProps =
	| {
			taskRun: TaskRunCardData;
	  }
	| {
			taskRun: TaskRunCardData;
			checked: boolean;
			onCheckedChange: (checked: boolean) => void;
	  };

export const TaskRunCard = ({ taskRun, ...props }: TaskRunCardProps) => {
	return (
		<Card className={stateCardVariants({ state: taskRun.state?.type })}>
			<div className="flex justify-between items-center">
				<div className="flex items-center gap-2">
					{"checked" in props && "onCheckedChange" in props && (
						<Checkbox
							checked={props.checked}
							onCheckedChange={props.onCheckedChange}
						/>
					)}
					<TaskRunName taskRun={taskRun} />
				</div>
				<div>
					<TagBadgeGroup tags={taskRun.tags} />
				</div>
			</div>
			<div className="flex items-center gap-2">
				{taskRun.state && (
					<StateBadge type={taskRun.state.type} name={taskRun.state.name} />
				)}
				<TaskRunStartTime taskRun={taskRun} />
				{taskRun.state?.type !== "SCHEDULED" && (
					<TaskRunDuration taskRun={taskRun} />
				)}
			</div>
			{taskRun.flow_run_name && taskRun.flow_run_id && (
				<div className="flex items-center gap-2">
					<TaskRunFlowRun taskRun={taskRun} />
				</div>
			)}
		</Card>
	);
};

type TaskRunNameProps = {
	taskRun: TaskRunCardData;
};

const TaskRunName = ({ taskRun }: TaskRunNameProps) => {
	return (
		<Link
			to="/runs/task-run/$id"
			params={{ id: taskRun.id }}
			className="text-sm font-medium hover:underline"
		>
			{taskRun.name}
		</Link>
	);
};

type TaskRunStartTimeProps = {
	taskRun: TaskRunCardData;
};

const TaskRunStartTime = ({ taskRun }: TaskRunStartTimeProps) => {
	const { start_time, expected_start_time, estimated_start_time_delta } =
		taskRun;

	let text: string | undefined;
	let tooltipText: string | undefined;
	if (start_time) {
		text = `${formatDate(start_time, "dateTimeNumeric")} ${getDelta(estimated_start_time_delta)}`;
		tooltipText = new Date(start_time).toString();
	} else if (expected_start_time) {
		text = `Scheduled for ${formatDate(expected_start_time, "dateTimeNumeric")} ${getDelta(estimated_start_time_delta)}`;
		tooltipText = new Date(expected_start_time).toString();
	}

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

const getDelta = (estimated_start_time_delta: null | number | undefined) => {
	if (!estimated_start_time_delta || estimated_start_time_delta <= 60) {
		return "";
	}
	return `(${humanizeDuration(estimated_start_time_delta, { maxDecimalPoints: 0 })} late)`;
};

type TaskRunDurationProps = {
	taskRun: TaskRunCardData;
};

const TaskRunDuration = ({ taskRun }: TaskRunDurationProps) => {
	const { estimated_run_time, total_run_time } = taskRun;
	const duration = estimated_run_time || total_run_time;
	const durationLabel = humanizeDuration(duration, {
		maxDecimalPoints: 2,
		units: ["s"],
	});
	const durationTooltip = humanizeDuration(duration, {
		maxDecimalPoints: 5,
		units: ["s"],
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

type TaskRunFlowRunProps = {
	taskRun: TaskRunCardData;
};

const TaskRunFlowRun = ({ taskRun }: TaskRunFlowRunProps) => {
	if (!taskRun.flow_run_id || !taskRun.flow_run_name) {
		return null;
	}

	return (
		<div className="flex items-center gap-1 text-xs text-muted-foreground">
			<Icon id="GitBranch" className="size-4" />
			<span>Flow run:</span>
			<Link
				to="/runs/flow-run/$id"
				params={{ id: taskRun.flow_run_id }}
				className="hover:underline text-blue-600"
			>
				{taskRun.flow_run_name}
			</Link>
		</div>
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
