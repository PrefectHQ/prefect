import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { secondsToApproximateString, secondsToString } from "@/utils/seconds";

type FlowRunDurationProps = {
	flowRun: FlowRunCardData;
};

export const FlowRunDuration = ({ flowRun }: FlowRunDurationProps) => {
	const { estimated_run_time, total_run_time } = flowRun;
	const duration = estimated_run_time || total_run_time;
	const durationLabel = secondsToApproximateString(duration);
	const durationTooltip = secondsToString(duration);

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
