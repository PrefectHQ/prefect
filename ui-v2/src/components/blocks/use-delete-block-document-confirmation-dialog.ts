import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
	type BlockDocument,
	useDeleteBlockDocument,
} from "@/api/block-documents";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

export const useDeleteBlockDocumentConfirmationDialog = () => {
	const navigate = useNavigate();
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { deleteBlockDocument, mutateAsync } = useDeleteBlockDocument();

	const handleConfirmDelete = (
		/** Pass a block document or list of block document ids for bulk edit */
		blockDocument: BlockDocument | Array<string>,
		{
			shouldNavigate = false,
			onSuccess = () => {},
		}: {
			/** Should navigate back to /blocks */
			shouldNavigate?: boolean;
			onSuccess?: () => void;
		} = {},
	) => {
		if (Array.isArray(blockDocument)) {
			const handleDeleteBlockDocuments = async () => {
				try {
					await Promise.all(blockDocument.map((id) => mutateAsync(id)));
					toast.success("Blocks deleted");
					if (shouldNavigate) {
						void navigate({ to: "/blocks" });
					}
				} catch (error) {
					const message =
						error instanceof Error
							? error.message
							: "Unknown error while deleting block.";
					toast.error(message);
					console.error(message);
				}
			};

			const description =
				blockDocument.length > 1
					? `Are you sure you want to delete these ${blockDocument.length} selected blocks?`
					: "Are you sure you want to delete this selected block?";

			confirmDelete({
				title: "Delete Blocks",
				description,
				onConfirm: () => {
					void handleDeleteBlockDocuments();
					onSuccess();
				},
			});
		} else {
			confirmDelete({
				title: "Delete Block",
				description: `Are you sure you want to delete ${blockDocument.name ? blockDocument.name : "this block"}?`,
				onConfirm: () => {
					deleteBlockDocument(blockDocument.id, {
						onSuccess: () => {
							toast.success("Block deleted");
							if (shouldNavigate) {
								void navigate({ to: "/blocks" });
							}
							onSuccess();
						},
						onError: (error) => {
							const message =
								error.message || "Unknown error while deleting block.";
							toast.error(message);
							console.error(message);
						},
					});
				},
			});
		}
	};

	return [dialogState, handleConfirmDelete] as const;
};
