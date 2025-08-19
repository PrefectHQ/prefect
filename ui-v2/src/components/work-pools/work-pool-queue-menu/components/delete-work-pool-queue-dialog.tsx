import { toast } from "sonner";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { useDeleteWorkPoolQueueMutation } from "@/api/work-pool-queues";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

type DeleteWorkPoolQueueDialogProps = {
	queue: WorkPoolQueue;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onDeleted?: () => void;
};

export const DeleteWorkPoolQueueDialog = ({
	queue,
	open,
	onOpenChange,
	onDeleted,
}: DeleteWorkPoolQueueDialogProps) => {
	const deleteQueueMutation = useDeleteWorkPoolQueueMutation();

	const handleDelete = () => {
		if (!queue.work_pool_name) {
			toast.error("Work pool name is required");
			return;
		}

		deleteQueueMutation.mutate(
			{ workPoolName: queue.work_pool_name, queueName: queue.name },
			{
				onSuccess: () => {
					toast.success("Work pool queue deleted successfully");
					onDeleted?.();
					onOpenChange(false);
				},
				onError: () => {
					toast.error("Failed to delete work pool queue");
				},
			},
		);
	};

	return (
		<DeleteConfirmationDialog
			isOpen={open}
			title="Delete Work Pool Queue"
			description={`Are you sure you want to delete the work pool queue "${queue.name}"? This action cannot be undone.`}
			confirmText={queue.name}
			isLoading={deleteQueueMutation.isPending}
			loadingText="Deleting..."
			onConfirm={handleDelete}
			onClose={() => onOpenChange(false)}
		/>
	);
};
