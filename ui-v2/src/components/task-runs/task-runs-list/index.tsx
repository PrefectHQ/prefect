import { Link } from "@tanstack/react-router";
import { cva } from "class-variance-authority";
import humanizeDuration from "humanize-duration";
import type { components } from "@/api/prefect";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDate } from "@/utils/date";

type TaskRunResponse = components["schemas"]["TaskRunResponse"];

type TaskRunsListProps = {
	taskRuns: TaskRunResponse[];
};

export const TaskRunsList = ({ taskRuns }: TaskRunsListProps) => {
	return (
		<div className="flex flex-col gap-2">
			{taskRuns.map((taskRun) => (
				<TaskRunCard key={taskRun.id} taskRun={taskRun} />
			))}
		</div>
	);
};

type TaskRunCardProps = {
	taskRun: TaskRunResponse;
};

const TaskRunCard = ({ taskRun }: TaskRunCardProps) => {
	return (
		<Card className={stateCardVariants({ state: taskRun.state?.type })}>
			<div className="flex justify-between items-center">
				<TaskRunName taskRun={taskRun} />
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

const TaskRunName = ({ taskRun }: TaskRunCardProps) => {
	return (
		<Link
			to="/runs/task-run/$id"
			params={{ id: taskRun.id }}
			className="text-sm font-medium hover:underline"
		>
			{taskRun.name ?? "Unnamed task run"}
		</Link>
	);
};

const TaskRunStartTime = ({ taskRun }: TaskRunCardProps) => {
	const startTime =
		taskRun.state?.timestamp ??
		(taskRun.state?.type === "SCHEDULED" ? taskRun.created : null);

	if (!startTime) {
		return null;
	}

	const tooltipText = new Date(startTime).toString();

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<div className="text-xs font-mono flex gap-2 items-center">
						<Icon id="Calendar" className="size-4" />
						{formatDate(startTime, "dateTimeNumeric")}
					</div>
				</TooltipTrigger>
				<TooltipContent>{tooltipText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

const TaskRunDuration = ({ taskRun }: TaskRunCardProps) => {
	if (
		taskRun.state?.type === "SCHEDULED" ||
		taskRun.state?.type === "PENDING"
	) {
		return null;
	}

	const startTime = taskRun.state?.timestamp;
	if (!startTime) {
		return null;
	}

	const startDate = new Date(startTime);
	const now = new Date();
	const durationMs = now.getTime() - startDate.getTime();

	if (durationMs <= 0) {
		return null;
	}

	const durationLabel = humanizeDuration(durationMs, {
		maxDecimalPoints: 2,
		units: ["s"],
		round: true,
	});
	const durationTooltip = humanizeDuration(durationMs, {
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
