import { AlertCircle, CheckCircle, PauseCircle } from "lucide-react";
import type { WorkPoolQueueStatus } from "@/api/work-pool-queues";
import { Badge } from "@/components/ui/badge";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type WorkPoolQueueStatusBadgeProps = {
	status: WorkPoolQueueStatus;
	className?: string;
};

const statusConfig = {
	READY: {
		icon: CheckCircle,
		label: "Ready",
		iconColor: "text-green-600",
		tooltip:
			"Work queue has at least one actively polling worker ready to execute work.",
	},
	PAUSED: {
		icon: PauseCircle,
		label: "Paused",
		iconColor: "text-yellow-600",
		tooltip: "Work queue is paused. No work will be executed.",
	},
	NOT_READY: {
		icon: AlertCircle,
		label: "Not Ready",
		iconColor: "text-red-600",
		tooltip:
			"Work queue does not have any actively polling workers ready to execute work.",
	},
};

export const WorkPoolQueueStatusBadge = ({
	status,
	className,
}: WorkPoolQueueStatusBadgeProps) => {
	const config = statusConfig[status];
	const Icon = config.icon;

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<Badge
						variant="secondary"
						className={cn("flex items-center space-x-1 cursor-help", className)}
					>
						<Icon className={cn("h-3 w-3", config.iconColor)} />
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
