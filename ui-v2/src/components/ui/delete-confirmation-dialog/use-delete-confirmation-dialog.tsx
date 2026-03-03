import { useCallback, useState } from "react";
import type { DeleteConfirmationDialogProps } from "./delete-confirmation-dialog";

type DeleteConfig = {
	title?: string;
	description?: string;
	confirmText?: string;
	isLoading?: boolean;
	onConfirm: () => void;
};

export const useDeleteConfirmationDialog = () => {
	const [dialogState, setDialogState] = useState<DeleteConfirmationDialogProps>(
		{
			isOpen: false,
			title: "",
			description: "",
			onConfirm: () => {},
			onClose: () => setDialogState((prev) => ({ ...prev, isOpen: false })),
		},
	);

	const confirmDelete = useCallback(
		({
			title = "Confirm Deletion",
			description = "Are you sure you want to delete this item? This action cannot be undone.",
			confirmText,
			isLoading = false,
			onConfirm,
		}: DeleteConfig) => {
			const closeDialog = () =>
				setDialogState((prev) => ({ ...prev, isOpen: false }));
			setDialogState({
				isOpen: true,
				title,
				description,
				confirmText,
				isLoading,
				onConfirm: () => {
					onConfirm();
					closeDialog();
				},
				onClose: closeDialog,
			});
		},
		[],
	);

	return [dialogState, confirmDelete] as const;
};
