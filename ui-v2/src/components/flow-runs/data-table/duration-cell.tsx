import {
	type FlowRunWithDeploymentAndFlow,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import humanizeDuration from "humanize-duration";

type DurationCellProps = {
	flowRun: FlowRunWithFlow | FlowRunWithDeploymentAndFlow;
};

export const DurationCell = ({ flowRun }: DurationCellProps) => {
	const { estimated_run_time, total_run_time } = flowRun;
	const duration = estimated_run_time || total_run_time;
	const durationLabel = humanizeDuration(duration, {
		maxDecimalPoints: 2,
	});
	const durationTooltip = humanizeDuration(duration, {
		maxDecimalPoints: 5,
	});

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button variant="ghost">
						<div className="flex gap-2 items-center text-sm font-mono">
							<Icon id="Clock" className="h-4 w-4" />
							{durationLabel}
						</div>
					</Button>
				</TooltipTrigger>
				<TooltipContent>{durationTooltip}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
