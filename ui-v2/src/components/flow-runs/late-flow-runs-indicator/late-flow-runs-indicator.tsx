import { Clock } from "lucide-react";
import type { ReactElement } from "react";

import { Badge } from "@/components/ui/badge";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";

type LateFlowRunsIndicatorProps = {
	lateRunsCount: number;
	className?: string;
};

export const LateFlowRunsIndicator = ({
	lateRunsCount,
	className,
}: LateFlowRunsIndicatorProps): ReactElement | null => {
	if (lateRunsCount === 0) {
		return null;
	}

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant="warning"
						className={cn("flex items-center space-x-1", className)}
					>
						<Clock className="h-3 w-3" />
						<span>{lateRunsCount}</span>
					</Badge>
				</TooltipTrigger>
				<TooltipContent>
					<div className="space-y-1">
						<p className="font-semibold">Late Flow Runs</p>
						<p className="text-sm">
							{lateRunsCount} flow run{lateRunsCount === 1 ? "" : "s"} running
							late
						</p>
					</div>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
