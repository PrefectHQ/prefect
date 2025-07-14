import { toast } from "sonner";
import {
	type TaskRunConcurrencyLimit,
	useDeleteTaskRunConcurrencyLimit,
} from "@/api/task-run-concurrency-limits";
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

type TaskRunConcurrencyLimitsDeleteDialogProps = {
	data: TaskRunConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onDelete: () => void;
};

export const TaskRunConcurrencyLimitsDeleteDialog = ({
	data,
	onOpenChange,
	onDelete,
}: TaskRunConcurrencyLimitsDeleteDialogProps) => {
	const { deleteTaskRunConcurrencyLimit, isPending } =
		useDeleteTaskRunConcurrencyLimit();

	const handleOnClick = (id: string) => {
		deleteTaskRunConcurrencyLimit(id, {
			onSuccess: () => {
				toast.success("Concurrency limit deleted");
			},
			onError: (error) => {
				const message =
					error.message || "Unknown error while deleting concurrency limit.";
				console.error(message);
			},
			onSettled: onDelete,
		});
	};

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Delete Concurrency Limit</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					Are you sure you want to delete {data.tag}
				</DialogDescription>
				<DialogFooter>
					<DialogTrigger asChild>
						<Button variant="outline">Close</Button>
					</DialogTrigger>
					<Button
						variant="destructive"
						onClick={() => handleOnClick(data.id)}
						loading={isPending}
					>
						Delete
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
