import { BlockDocument, useDeleteBlockDocument } from "@/api/block-documents";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { getRouteApi } from "@tanstack/react-router";
import { toast } from "sonner";

const routeApi = getRouteApi("/blocks/");

export const useDeleteBlockDocumentConfirmationDialog = () => {
	const navigate = routeApi.useNavigate();
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { deleteBlockDocument } = useDeleteBlockDocument();

	const handleConfirmDelete = (
		blockDocument: BlockDocument,
		{
			shouldNavigate = false,
		}: {
			/** Should navigate back to /blocks */
			shouldNavigate?: boolean;
		} = {},
	) =>
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

	return [dialogState, handleConfirmDelete] as const;
};
