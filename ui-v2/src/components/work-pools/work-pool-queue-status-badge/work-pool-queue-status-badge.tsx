import { Pause } from "lucide-react";
import type { WorkPoolQueueStatus } from "@/api/work-pool-queues";
import { Badge } from "@/components/ui/badge";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";

type WorkPoolQueueStatusBadgeProps = {
	status: WorkPoolQueueStatus;
	className?: string;
};

const statusConfig = {
	READY: {
		label: "Ready",
		color: "bg-green-500",
		tooltip:
			"Work queue has at least one actively polling worker ready to execute work.",
	},
	PAUSED: {
		label: "Paused",
		color: "bg-yellow-500",
		tooltip: "Work queue is paused. No work will be executed.",
	},
	NOT_READY: {
		label: "Not Ready",
		color: "bg-red-500",
		tooltip:
			"Work queue does not have any actively polling workers ready to execute work.",
	},
};

export const WorkPoolQueueStatusBadge = ({
	status,
	className,
}: WorkPoolQueueStatusBadgeProps) => {
	const config = statusConfig[status];

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<Badge
						variant="secondary"
						className={cn("flex items-center space-x-1 cursor-help", className)}
					>
						{status === "PAUSED" ? (
							<Pause className="h-2 w-2 text-muted-foreground" />
						) : (
							<div className={cn("h-2 w-2 rounded-full", config.color)} />
						)}
						<span>{config.label}</span>
					</Badge>
				</TooltipTrigger>
				<TooltipContent>
					<p>{config.tooltip}</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
