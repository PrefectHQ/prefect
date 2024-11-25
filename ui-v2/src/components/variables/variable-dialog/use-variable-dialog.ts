import { useCallback, useState } from "react";
import type { VariableDialogProps } from "./variable-dialog";

export const useVariableDialog = () => {
	const handleVariableDialogOpenChange = useCallback((open: boolean) => {
		setDialogState((prev) => ({
			...prev,
			open,
		}));
	}, []);

	const [dialogState, setDialogState] = useState<VariableDialogProps>({
		open: false,
		onOpenChange: handleVariableDialogOpenChange,
	});

	const handleVariableAddOrEdit = useCallback(
		(variableToEdit?: VariableDialogProps["variableToEdit"]) => {
			setDialogState((prev) => ({
				...prev,
				open: true,
				variableToEdit,
			}));
		},
		[],
	);

	return [dialogState, handleVariableAddOrEdit] as const;
};
