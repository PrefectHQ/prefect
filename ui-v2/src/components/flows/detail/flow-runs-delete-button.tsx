import { useDeleteFlowRunsDialog } from "@/components/flow-runs/flow-runs-list/use-delete-flow-runs-dialog";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";

type FlowRunsDeleteButtonProps = {
	selected: string[];
	onDelete: () => void;
};

export const FlowRunsDeleteButton = ({
	selected,
	onDelete,
}: FlowRunsDeleteButtonProps) => {
	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteFlowRunsDialog();

	if (selected.length === 0) {
		return null;
	}

	return (
		<>
			<Button
				variant="ghost"
				size="sm"
				onClick={() => confirmDelete(selected, onDelete)}
				className="ml-2"
				aria-label="Delete selected flow runs"
			>
				<Icon id="Trash2" className="h-4 w-4" />
			</Button>
			<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
		</>
	);
};
