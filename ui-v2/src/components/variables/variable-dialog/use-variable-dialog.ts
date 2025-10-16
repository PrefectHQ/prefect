import { useState } from "react";
import type { VariableDialogProps } from "./variable-dialog";

export const useVariableDialog = () => {
	const [dialogState, setDialogState] = useState<VariableDialogProps>({
		open: false,
		onOpenChange: (open: boolean) => {
			setDialogState((prev) => ({
				...prev,
				open,
			}));
		},
	});

	const handleVariableAddOrEdit = (
		variableToEdit?: VariableDialogProps["variableToEdit"],
	) => {
		setDialogState((prev) => ({
			...prev,
			open: true,
			variableToEdit,
		}));
	};

	return [dialogState, handleVariableAddOrEdit] as const;
};
