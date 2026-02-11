import { useCallback, useState } from "react";

export type UseChangeStateDialogResult = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	openDialog: () => void;
	closeDialog: () => void;
};

export const useChangeStateDialog = (): UseChangeStateDialogResult => {
	const [open, setOpen] = useState(false);

	const openDialog = useCallback(() => setOpen(true), []);
	const closeDialog = useCallback(() => setOpen(false), []);

	return {
		open,
		onOpenChange: setOpen,
		openDialog,
		closeDialog,
	};
};
