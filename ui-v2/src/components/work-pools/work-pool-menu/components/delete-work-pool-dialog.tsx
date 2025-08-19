import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import { useDeleteWorkPool } from "@/api/work-pools";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

type DeleteWorkPoolDialogProps = {
	workPool: WorkPool;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onDeleted?: () => void;
};

export const DeleteWorkPoolDialog = ({
	workPool,
	open,
	onOpenChange,
	onDeleted,
}: DeleteWorkPoolDialogProps) => {
	const navigate = useNavigate();
	const { deleteWorkPool, isPending } = useDeleteWorkPool();

	const handleDelete = () => {
		deleteWorkPool(workPool.name, {
			onSuccess: () => {
				toast.success("Work pool deleted successfully");
				onDeleted?.();
				void navigate({ to: "/work-pools" });
			},
			onError: () => {
				toast.error("Failed to delete work pool");
			},
		});
	};

	return (
		<DeleteConfirmationDialog
			isOpen={open}
			title="Delete Work Pool"
			description={`Are you sure you want to delete the work pool "${workPool.name}"? This action cannot be undone.`}
			confirmText={workPool.name}
			isLoading={isPending}
			loadingText="Deleting..."
			onConfirm={handleDelete}
			onClose={() => onOpenChange(false)}
		/>
	);
};
