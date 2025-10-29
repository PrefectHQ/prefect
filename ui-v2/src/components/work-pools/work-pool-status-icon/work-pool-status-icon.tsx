import { CircleDot, PauseCircle } from "lucide-react";
import type { WorkPoolStatus } from "@/api/work-pools";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";

type WorkPoolStatusIconProps = {
	status: WorkPoolStatus;
	showTooltip?: boolean;
	className?: string;
};

const statusIconMap = {
	READY: CircleDot,
	PAUSED: PauseCircle,
	NOT_READY: CircleDot,
} as const;

const statusColorMap = {
	READY: "text-green-600",
	PAUSED: "text-yellow-600",
	NOT_READY: "text-red-600",
} as const;

const getStatusDescription = (status: WorkPoolStatus): string => {
	switch (status) {
		case "READY":
			return "Work pool is ready and accepting work";
		case "PAUSED":
			return "Work pool is paused";
		case "NOT_READY":
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

	const shouldFill = status === "READY" || status === "NOT_READY";
	const icon = (
		<Icon
			className={cn("h-3 w-3", colorClass, className)}
			fill={shouldFill ? "currentColor" : "none"}
		/>
	);

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
