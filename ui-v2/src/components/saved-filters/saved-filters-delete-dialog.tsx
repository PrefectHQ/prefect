import { toast } from "sonner";
import { useDeleteSavedSearch } from "@/api/saved-searches";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import type { SavedFlowRunsSearch } from "./saved-filters";

type SavedFiltersDeleteDialogProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	savedSearch: SavedFlowRunsSearch;
	onDeleted?: () => void;
};

export function SavedFiltersDeleteDialog({
	open,
	onOpenChange,
	savedSearch,
	onDeleted,
}: SavedFiltersDeleteDialogProps) {
	const { deleteSavedSearch, isPending } = useDeleteSavedSearch();

	const handleConfirm = () => {
		if (!savedSearch.id) {
			return;
		}

		deleteSavedSearch(savedSearch.id, {
			onSuccess: () => {
				toast.success("View deleted successfully");
				onOpenChange(false);
				onDeleted?.();
			},
			onError: (error) => {
				toast.error(
					error instanceof Error ? error.message : "Failed to delete view",
				);
			},
		});
	};

	return (
		<DeleteConfirmationDialog
			isOpen={open}
			title="Delete Saved View"
			description={`Are you sure you want to delete "${savedSearch.name}"? This action cannot be undone.`}
			onConfirm={handleConfirm}
			onClose={() => onOpenChange(false)}
			isLoading={isPending}
		/>
	);
}
