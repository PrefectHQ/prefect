import { CircleDot, PauseCircle } from "lucide-react";
import type {
	WorkPoolQueue,
	WorkPoolQueueStatus,
} from "@/api/work-pool-queues";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";

type WorkPoolQueueStatusIconProps = {
	queue: WorkPoolQueue;
	className?: string;
};

const statusIconMap = {
	READY: CircleDot,
	PAUSED: PauseCircle,
	NOT_READY: CircleDot,
} as const;

const statusColorMap = {
	READY: "text-green-600",
	PAUSED: "text-muted-foreground",
	NOT_READY: "text-red-600",
} as const;

const getStatusDescription = (
	status: WorkPoolQueueStatus,
	isPushPool: boolean,
): string => {
	switch (status) {
		case "READY":
			return isPushPool
				? "Work queue is ready."
				: "Work queue has at least one actively polling worker ready to execute work.";
		case "PAUSED":
			return "Work queue is paused. No work will be executed.";
		case "NOT_READY":
			return "Work queue does not have any actively polling workers ready to execute work.";
	}
};

const getStatus = (queue: WorkPoolQueue): WorkPoolQueueStatus => {
	if (queue.is_paused) return "PAUSED";
	return (queue.status?.toUpperCase() as WorkPoolQueueStatus) ?? "READY";
};

export const WorkPoolQueueStatusIcon = ({
	queue,
	className,
}: WorkPoolQueueStatusIconProps) => {
	const status = getStatus(queue);
	const description = getStatusDescription(status, false); // TODO: Get isPushPool from work pool context if needed
	const Icon = statusIconMap[status];
	const colorClass = statusColorMap[status];

	const shouldFill = status === "READY" || status === "NOT_READY";
	const icon = (
		<Icon
			className={cn("h-3 w-3", colorClass, className)}
			fill={shouldFill ? "currentColor" : "none"}
		/>
	);

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>{icon}</TooltipTrigger>
				<TooltipContent>
					<p>{description}</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
