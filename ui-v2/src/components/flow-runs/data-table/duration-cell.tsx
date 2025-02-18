import {
	type FlowRunWithDeploymentAndFlow,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { Typography } from "@/components/ui/typography";
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
					<div className="flex items-center">
						<div className="flex items-center gap-1">
							<Icon id="Clock" className="h-4 w-4" />
							<Typography variant="bodySmall">{durationLabel}</Typography>
						</div>
					</div>
				</TooltipTrigger>
				<TooltipContent>{durationTooltip}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
