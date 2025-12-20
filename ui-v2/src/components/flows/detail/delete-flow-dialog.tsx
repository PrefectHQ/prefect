import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import type { Flow } from "@/api/flows";
import { useDeleteFlowById } from "@/api/flows";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

type DeleteFlowDialogProps = {
	flow: Flow;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onDeleted?: () => void;
};

export const DeleteFlowDialog = ({
	flow,
	open,
	onOpenChange,
	onDeleted,
}: DeleteFlowDialogProps) => {
	const navigate = useNavigate();
	const { deleteFlow, isPending } = useDeleteFlowById();

	const handleDelete = () => {
		deleteFlow(flow.id, {
			onSuccess: () => {
				toast.success("Flow deleted");
				onDeleted?.();
				void navigate({ to: "/flows" });
			},
			onError: () => {
				toast.error("Failed to delete flow");
			},
		});
	};

	return (
		<DeleteConfirmationDialog
			isOpen={open}
			title="Delete Flow"
			description={`Are you sure you want to delete ${flow.name}? This action cannot be undone.`}
			isLoading={isPending}
			loadingText="Deleting..."
			onConfirm={handleDelete}
			onClose={() => onOpenChange(false)}
		/>
	);
};
