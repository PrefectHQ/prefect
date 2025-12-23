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
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StateBadge } from "@/components/ui/state-badge";

type FlowRunHeaderProps = {
	flowRun: FlowRun;
	onDeleteClick: () => void;
};

export function FlowRunHeader({ flowRun, onDeleteClick }: FlowRunHeaderProps) {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	return (
		<div className="flex flex-row justify-between">
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
						{flowRun.state_type && flowRun.state_name && (
							<StateBadge
								type={flowRun.state_type}
								name={flowRun.state_name}
								className="ml-2"
							/>
						)}
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
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
					<DropdownMenuItem
						onClick={() =>
							confirmDelete({
								title: "Delete Flow Run",
								description: `Are you sure you want to delete flow run ${flowRun.name}?`,
								onConfirm: onDeleteClick,
							})
						}
					>
						Delete
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			<DeleteConfirmationDialog {...dialogState} />
		</div>
	);
}
