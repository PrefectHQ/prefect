import { toast } from "sonner";
import { useDeleteVariable, type Variable } from "@/api/variables";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

export const useDeleteVariableConfirmationDialog = () => {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { deleteVariable } = useDeleteVariable();

	const handleConfirmDelete = (variable: Variable) =>
		confirmDelete({
			title: "Delete Variable",
			description: `Are you sure you want to delete ${variable.name}? This action cannot be undone.`,
			onConfirm: () => {
				const id = variable.id;
				if (!id) return;
				deleteVariable(id, {
					onSuccess: () => {
						toast.success("Variable deleted");
					},
					onError: (error) => {
						const message =
							error.message || "Unknown error while deleting variable.";
						console.error(message);
					},
				});
			},
		});

	return [dialogState, handleConfirmDelete] as const;
};
