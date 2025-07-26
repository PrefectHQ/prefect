import { AlertCircle, CheckCircle, PauseCircle } from "lucide-react";

import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { getWorkPoolStatusInfo, type WorkPoolStatus } from "@/lib/work-pools";

interface WorkPoolStatusIconProps {
	status: WorkPoolStatus;
	showTooltip?: boolean;
	className?: string;
}

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

export const WorkPoolStatusIcon = ({
	status,
	showTooltip = true,
	className,
}: WorkPoolStatusIconProps) => {
	const statusInfo = getWorkPoolStatusInfo(status);
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
					<p>{statusInfo.description}</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
