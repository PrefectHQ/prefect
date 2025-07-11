import { toast } from "sonner";
import type { DeploymentSchedule } from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { useDeleteSchedule } from "./use-delete-schedule";

type ScheduleActionMenuProps = {
	deploymentSchedule: DeploymentSchedule;
	onEditSchedule: (scheduleId: string) => void;
};

export const ScheduleActionMenu = ({
	deploymentSchedule,
	onEditSchedule,
}: ScheduleActionMenuProps) => {
	const [dialogState, confirmDelete] = useDeleteSchedule();
	const handleCopyId = (id: string) => {
		void navigator.clipboard.writeText(id);
		toast.success("ID copied");
	};

	const handleDelete = () => confirmDelete(deploymentSchedule);
	const handleEdit = () => onEditSchedule(deploymentSchedule.id);

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="size-8 p-0">
						<span className="sr-only">Open menu</span>
						<Icon id="MoreVertical" className="size-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuLabel>Actions</DropdownMenuLabel>
					<DropdownMenuItem onClick={() => handleCopyId(deploymentSchedule.id)}>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem onClick={handleEdit}>Edit</DropdownMenuItem>
					<DropdownMenuItem onClick={handleDelete}>Delete</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};
