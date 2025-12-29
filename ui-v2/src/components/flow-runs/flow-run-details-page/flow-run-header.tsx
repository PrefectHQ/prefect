import { Link } from "@tanstack/react-router";
import { MoreVertical } from "lucide-react";
import { toast } from "sonner";
import type { FlowRun } from "@/api/flow-runs";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
	DeleteConfirmationDialog,
	useDeleteConfirmationDialog,
} from "@/components/ui/delete-confirmation-dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RunStateChangeDialog } from "@/components/ui/run-state-change-dialog";
import { StateBadge } from "@/components/ui/state-badge";
import { useFlowRunStateDialog } from "../flow-run-state-dialog/use-flow-run-state-dialog";

type FlowRunHeaderProps = {
	flowRun: FlowRun;
	onDeleteClick: () => void;
};

export function FlowRunHeader({ flowRun, onDeleteClick }: FlowRunHeaderProps) {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();
	const { dialogProps, openDialog } = useFlowRunStateDialog(flowRun);

	return (
		<div className="flex flex-col gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem>
						<BreadcrumbLink to="/runs" className="text-xl font-semibold">
							Runs
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem className="text-xl">
						<BreadcrumbPage className="font-semibold">
							{flowRun.name}
						</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>

			<div className="flex items-center justify-between">
				<div className="flex items-center gap-2">
					<h1 className="text-2xl font-semibold">{flowRun.name}</h1>
					{flowRun.state_type && flowRun.state_name && (
						<StateBadge type={flowRun.state_type} name={flowRun.state_name} />
					)}
					{flowRun.flow_id && (
						<Link
							to="/flows/flow/$id"
							params={{ id: flowRun.flow_id }}
							className="text-sm text-muted-foreground hover:underline"
						>
							View Flow
						</Link>
					)}
					{flowRun.deployment_id && (
						<Link
							to="/deployments/deployment/$id"
							params={{ id: flowRun.deployment_id }}
							className="text-sm text-muted-foreground hover:underline"
						>
							View Deployment
						</Link>
					)}
				</div>

				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="outline" className="p-2">
							<MoreVertical className="w-4 h-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent>
						<DropdownMenuItem
							onClick={() => {
								void navigator.clipboard.writeText(flowRun.id);
								toast.success("Copied flow run ID to clipboard");
							}}
						>
							Copy ID
						</DropdownMenuItem>
						<DropdownMenuItem onClick={openDialog}>
							Change State
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							onClick={() =>
								confirmDelete({
									title: "Delete Flow Run",
									description: `Are you sure you want to delete flow run ${flowRun.name}?`,
									onConfirm: onDeleteClick,
								})
							}
							variant="destructive"
						>
							Delete
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>

			<DeleteConfirmationDialog {...dialogState} />
			<RunStateChangeDialog {...dialogProps} />
		</div>
	);
}
