import { toast } from "sonner";
import type { WorkPoolWorker } from "@/api/work-pools";
import { useDeleteWorker } from "@/api/work-pools";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

type DeleteWorkerDialogProps = {
	worker: WorkPoolWorker;
	workPoolName: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onDeleted?: () => void;
};

export const DeleteWorkerDialog = ({
	worker,
	workPoolName,
	open,
	onOpenChange,
	onDeleted,
}: DeleteWorkerDialogProps) => {
	const { deleteWorker, isPending } = useDeleteWorker();

	const handleDelete = () => {
		deleteWorker(
			{
				workPoolName,
				workerName: worker.name,
			},
			{
				onSuccess: () => {
					toast.success("Worker deleted successfully");
					onDeleted?.();
					onOpenChange(false);
				},
				onError: () => {
					toast.error("Failed to delete worker");
				},
			},
		);
	};

	return (
		<DeleteConfirmationDialog
			isOpen={open}
			title="Delete Worker"
			description={`Are you sure you want to delete the worker "${worker.name}"? This action cannot be undone.`}
			confirmText={worker.name}
			isLoading={isPending}
			loadingText="Deleting..."
			onConfirm={handleDelete}
			onClose={() => onOpenChange(false)}
		/>
	);
};
