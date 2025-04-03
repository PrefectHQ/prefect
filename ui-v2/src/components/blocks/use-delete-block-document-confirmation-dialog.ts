import { BlockDocument, useDeleteBlockDocument } from "@/api/block-documents";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { getRouteApi } from "@tanstack/react-router";
import { toast } from "sonner";

const routeApi = getRouteApi("/blocks/");

export const useDeleteBlockDocumentConfirmationDialog = () => {
	const navigate = routeApi.useNavigate();
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { deleteBlockDocument, mutateAsync } = useDeleteBlockDocument();

	const handleConfirmDelete = (
		/** Pass a block document or list of block document ids for bulk edit */
		blockDocument: BlockDocument | Array<string>,
		{
			shouldNavigate = false,
		}: {
			/** Should navigate back to /blocks */
			shouldNavigate?: boolean;
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
				blockDocument.length > 0
					? `Are you sure you want to delete these ${blockDocument.length} selected blocks?`
					: "Are you sure you want to delete this selectged block?";

			confirmDelete({
				title: "Delete Blocks",
				description,
				onConfirm: () => {
					void handleDeleteBlockDocuments();
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
