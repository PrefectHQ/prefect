import { DropdownMenuItem } from "@/components/ui/dropdown-menu";

import type { DeploymentWithFlow } from "@/api/deployments";
import { buildListFlowRunsQuery } from "@/api/flow-runs";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import { Icon } from "@/components/ui/icons";
import useDebounce from "@/hooks/use-debounce";
import { useToast } from "@/hooks/use-toast";
import { useQuery } from "@tanstack/react-query";
import type { CellContext } from "@tanstack/react-table";
import { subSeconds } from "date-fns";
import { secondsInWeek } from "date-fns/constants";
import { useCallback, useState } from "react";

type ActionsCellProps = CellContext<DeploymentWithFlow, unknown> & {
	onQuickRun: (deployment: DeploymentWithFlow) => void;
	onCustomRun: (deployment: DeploymentWithFlow) => void;
	onEdit: (deployment: DeploymentWithFlow) => void;
	onDelete: (deployment: DeploymentWithFlow) => void;
	onDuplicate: (deployment: DeploymentWithFlow) => void;
};

export const ActionsCell = ({
	row,
	onQuickRun,
	onCustomRun,
	onEdit,
	onDelete,
	onDuplicate,
}: ActionsCellProps) => {
	const id = row.original.id;
	const { toast } = useToast();
	if (!id) return null;

	return (
		<div className="flex flex-row justify-end">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<Icon id="MoreVertical" className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuLabel>Actions</DropdownMenuLabel>
					<DropdownMenuItem onClick={() => onQuickRun(row.original)}>
						Quick Run
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onCustomRun(row.original)}>
						Custom Run
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							void navigator.clipboard.writeText(id);
							toast({
								title: "ID copied",
							});
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onEdit(row.original)}>
						Edit
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onDelete(row.original)}>
						Delete
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onDuplicate(row.original)}>
						Duplicate
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
};

const BAR_WIDTH = 8;
const BAR_GAP = 4;

export const ActivityCell = ({
	row,
}: CellContext<DeploymentWithFlow, unknown>) => {
	const [numberOfBars, setNumberOfBars] = useState<number>(0);
	const debouncedNumberOfBars = useDebounce(numberOfBars, 150);

	const chartRef = useCallback((node: HTMLDivElement | null) => {
		if (!node) return;

		const updateBars = () => {
			const chartWidth = node.getBoundingClientRect().width;
			setNumberOfBars(Math.floor(chartWidth / (BAR_WIDTH + BAR_GAP)));
		};

		// Set the initial number of bars based on the chart width
		updateBars();

		// Observe the chart for resize events
		const resizeObserver = new ResizeObserver(updateBars);
		resizeObserver.observe(node);
		return () => {
			// Clean up the observer
			resizeObserver.disconnect();
		};
	}, []);

	const { data: flowRuns } = useQuery(
		buildListFlowRunsQuery({
			deployments: {
				operator: "and_",
				id: {
					any_: [row.original.id],
				},
			},
			sort: "START_TIME_DESC",
			limit: debouncedNumberOfBars || numberOfBars,
			offset: 0,
		}),
	);

	const { flow, ...deployment } = row.original;
	const enrichedFlowRuns =
		flowRuns?.map((flowRun) => ({
			...flowRun,
			deployment,
			flow,
		})) ?? [];

	return (
		<div className="w-full" ref={chartRef}>
			<FlowRunActivityBarChart
				startDate={subSeconds(new Date(), secondsInWeek)}
				endDate={new Date()}
				// If debouncedNumberOfBars is 0, use numberOfBars for an asymmetric debounce to avoid rendering an empty chart on initial paint.
				numberOfBars={debouncedNumberOfBars || numberOfBars}
				barWidth={BAR_WIDTH}
				enrichedFlowRuns={enrichedFlowRuns}
				className="h-12 w-full"
				chartId={row.original.id}
			/>
		</div>
	);
};
