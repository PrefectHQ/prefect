import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { MoreVerticalIcon } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { CellContext } from "@tanstack/react-table";
import type { DeploymentWithFlowName } from "./types";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-chart";

export const ActionsCell = ({
	row,
}: CellContext<DeploymentWithFlowName, unknown>) => {
	const { toast } = useToast();

	return (
		<div className="flex flex-row justify-end">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<MoreVerticalIcon className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuLabel>Actions</DropdownMenuLabel>
					<DropdownMenuItem>Quick Run</DropdownMenuItem>
					<DropdownMenuItem>Custom Run</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							if (row.original.id) {
								void navigator.clipboard.writeText(row.original.id);
								toast({
									title: "ID copied",
								});
							}
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem>Edit</DropdownMenuItem>
					<DropdownMenuItem>Delete</DropdownMenuItem>
					<DropdownMenuItem>Duplicate</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
};

export const ActivityCell = ({
	row,
}: CellContext<DeploymentWithFlowName, unknown>) => {
	return (
		<FlowRunActivityBarChart
			flowRuns={[]}
			startDate={new Date()}
			endDate={new Date()}
			className="h-8 w-full"
		/>
	);
};
