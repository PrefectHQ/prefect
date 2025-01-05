import { DropdownMenuItem } from "@/components/ui/dropdown-menu";

import { DeploymentWithFlow } from "@/api/deployments";
import { FlowRunWithDeploymentAndFlow } from "@/api/flow-runs";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-acitivity-bar-graph";
import { Icon } from "@/components/ui/icons";
import { useToast } from "@/hooks/use-toast";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
} from "@/mocks";
import type { CellContext } from "@tanstack/react-table";
import { useEffect, useRef, useState } from "react";

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

// TODO: Remove this once we have a real implementation
const createFakeFlowRunWithDeploymentAndFlow =
	(): FlowRunWithDeploymentAndFlow => {
		const flowRun = createFakeFlowRun();

		return {
			...flowRun,
			deployment: createFakeDeployment(),
			flow: createFakeFlow(),
		};
	};

const BAR_WIDTH = 8;
const BAR_GAP = 4;

export const ActivityCell = ({
	row,
}: CellContext<DeploymentWithFlow, unknown>) => {
	const chartRef = useRef<HTMLDivElement>(null);
	const [numberOfBars, setNumberOfBars] = useState(0);

	useEffect(() => {
		const element = chartRef.current;
		if (!element) return;

		const updateBars = () => {
			const chartWidth = element.getBoundingClientRect().width;
			setNumberOfBars(Math.floor(chartWidth / (BAR_WIDTH + BAR_GAP)));
		};

		updateBars();

		const resizeObserver = new ResizeObserver(updateBars);
		resizeObserver.observe(element);

		return () => {
			resizeObserver.disconnect();
		};
	}, []);

	// TODO: Replace with an API call for flow runs
	const flowRuns = Array.from(
		{ length: numberOfBars },
		createFakeFlowRunWithDeploymentAndFlow,
	);
	return (
		<FlowRunActivityBarChart
			ref={chartRef}
			startDate={new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)}
			endDate={new Date()}
			numberOfBars={numberOfBars}
			barWidth={BAR_WIDTH}
			enrichedFlowRuns={flowRuns}
			className="h-8 w-full"
			chartId={row.original.id}
		/>
	);
};
