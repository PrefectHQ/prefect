import { TooltipContent, TooltipTrigger } from "@radix-ui/react-tooltip";
import type { FlowRun } from "@/api/flow-runs";
import { Tooltip } from "@/components/ui/tooltip";
import { Popover } from "./popover";

export type FlowRunCellProps = {
	flowRun: FlowRun | null;
	flowName: string;
	width: string;
	height: string;
	className?: string;
};

export const FlowRunCell = ({
	flowName,
	flowRun,
	width,
	height,
	className,
}: FlowRunCellProps) => {
	return (
		<Tooltip delayDuration={0}>
			<TooltipTrigger asChild>
				<div
					data-testid={`flow-run-cell-${flowRun?.id}`}
					className={className}
					style={{
						width: width,
						height: height,
						borderRadius: "4px",
						margin: "3px",
					}}
				/>
			</TooltipTrigger>
			<TooltipContent side="bottom" className="z-50">
				<Popover name={flowName} flowRun={flowRun} />
			</TooltipContent>
		</Tooltip>
	);
};
