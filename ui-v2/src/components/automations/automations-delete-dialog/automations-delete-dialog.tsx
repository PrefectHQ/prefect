import { toast } from "sonner";
import { type Automation, useDeleteAutomation } from "@/api/automations";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";

type AutomationsDeleteDialogProps = {
	automation: Automation;
	onOpenChange: (open: boolean) => void;
	onDelete: () => void;
};

export const AutomationsDeleteDialog = ({
	automation,
	onOpenChange,
	onDelete,
}: AutomationsDeleteDialogProps) => {
	const { deleteAutomation, isPending } = useDeleteAutomation();

	const handleOnClick = (id: string) => {
		deleteAutomation(id, {
			onSuccess: () => {
				toast.success("Automation deleted");
			},
			onError: (error) => {
				const message =
					error.message || "Unknown error while deleting automation.";
				console.error(message);
			},
			onSettled: onDelete,
		});
	};

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Delete Automation</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					Are you sure you want to delete {automation.name}
				</DialogDescription>
				<DialogFooter>
					<DialogTrigger asChild>
						<Button variant="outline">Close</Button>
					</DialogTrigger>
					<Button
						variant="destructive"
						onClick={() => handleOnClick(automation.id)}
						loading={isPending}
					>
						Delete
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
