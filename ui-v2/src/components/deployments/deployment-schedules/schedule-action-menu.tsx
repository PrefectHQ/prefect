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
import { useToast } from "@/hooks/use-toast";
import { DeploymentSchedule } from "./types";
import { useDeleteSchedule } from "./use-delete-schedule";

type ScheduleActionMenuProps = {
	deploymentSchedule: DeploymentSchedule;
};

export const ScheduleActionMenu = ({
	deploymentSchedule,
}: ScheduleActionMenuProps) => {
	const { toast } = useToast();
	const [dialogState, confirmDelete] = useDeleteSchedule();
	const handleCopyId = (id: string) => {
		void navigator.clipboard.writeText(id);
		toast({ title: "ID copied" });
	};

	const handleEdit = () => {};

	const handleDelete = () => confirmDelete(deploymentSchedule);

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<Icon id="MoreVertical" className="h-4 w-4" />
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
