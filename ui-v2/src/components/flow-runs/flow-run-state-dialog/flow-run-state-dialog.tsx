import { RunStateChangeDialog } from "@/components/ui/run-state-change-dialog";
import { useFlowRunStateDialog } from "./use-flow-run-state-dialog";

export const FlowRunStateDialog = () => {
	const { dialogProps } = useFlowRunStateDialog();

	if (!dialogProps) {
		return null;
	}

	return <RunStateChangeDialog {...dialogProps} />;
};
