import type { FlowRun } from "@/api/flow-runs";
import { useCallback, useState } from "react";
import type { FlowRunStateDialogProps } from "./flow-run-state-dialog";

export const useFlowRunStateDialog = () => {
	const handleDialogOpenChange = useCallback((open: boolean) => {
		setDialogState((prev) => ({
			...prev,
			open,
		}));
	}, []);

	const [dialogState, setDialogState] = useState<
		Omit<FlowRunStateDialogProps, "onOpenChange"> & {
			onOpenChange: (open: boolean) => void;
		}
	>({
		open: false,
		flowRun: {} as FlowRun, // Default empty flow run, will be replaced when opening dialog
		onOpenChange: handleDialogOpenChange,
	});

	const openFlowRunStateDialog = useCallback((flowRun: FlowRun) => {
		setDialogState((prev) => ({
			...prev,
			flowRun,
			open: true,
		}));
	}, []);

	return [dialogState, openFlowRunStateDialog] as const;
};
