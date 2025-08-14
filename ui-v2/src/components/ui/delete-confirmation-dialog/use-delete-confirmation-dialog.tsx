import { useCallback, useState } from "react";
import type { DeleteConfirmationDialogProps } from "./delete-confirmation-dialog";

type DeleteConfig = {
	title?: string;
	description?: string;
	confirmText?: string;
	isLoading?: boolean;
	loadingText?: string;
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
			loadingText = "Deleting...",
			onConfirm,
		}: DeleteConfig) => {
			setDialogState({
				isOpen: true,
				title,
				description,
				confirmText,
				isLoading,
				loadingText,
				onConfirm,
				onClose: () => setDialogState((prev) => ({ ...prev, isOpen: false })),
			});
		},
		[],
	);

	return [dialogState, confirmDelete] as const;
};
