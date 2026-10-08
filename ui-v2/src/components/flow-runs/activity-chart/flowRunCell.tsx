import { TooltipContent, TooltipTrigger } from "@radix-ui/react-tooltip";
import { Link } from "@tanstack/react-router";
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
	const cellProps = {
		"data-testid": `flow-run-cell-${flowRun?.id}`,
		className,
		style: {
			width,
			height,
			borderRadius: "4px",
			margin: "3px",
		},
	};

	return (
		<Tooltip delayDuration={0}>
			<TooltipTrigger asChild>
				{flowRun ? (
					<Link
						to="/runs/flow-run/$id"
						params={{ id: flowRun.id }}
						aria-label={`Open flow run ${flowRun.name}`}
						{...cellProps}
					/>
				) : (
					<div {...cellProps} />
				)}
			</TooltipTrigger>
			<TooltipContent side="bottom" className="z-50">
				<Popover name={flowName} flowRun={flowRun} />
			</TooltipContent>
		</Tooltip>
	);
};
