import { AlertCircle, CheckCircle, PauseCircle } from "lucide-react";

import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";
import type { WorkPoolStatus } from "../types";

export type { WorkPoolStatus };

type WorkPoolStatusIconProps = {
	status: WorkPoolStatus;
	showTooltip?: boolean;
	className?: string;
};

const statusIconMap = {
	ready: CheckCircle,
	paused: PauseCircle,
	not_ready: AlertCircle,
} as const;

const statusColorMap = {
	ready: "text-green-600",
	paused: "text-yellow-600",
	not_ready: "text-red-600",
} as const;

const getStatusDescription = (status: WorkPoolStatus): string => {
	switch (status) {
		case "ready":
			return "Work pool is ready and accepting work";
		case "paused":
			return "Work pool is paused";
		case "not_ready":
			return "Work pool is not ready";
	}
};

export const WorkPoolStatusIcon = ({
	status,
	showTooltip = true,
	className,
}: WorkPoolStatusIconProps) => {
	const description = getStatusDescription(status);
	const Icon = statusIconMap[status];
	const colorClass = statusColorMap[status];

	const icon = <Icon className={cn("h-4 w-4", colorClass, className)} />;

	if (!showTooltip) {
		return icon;
	}

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
