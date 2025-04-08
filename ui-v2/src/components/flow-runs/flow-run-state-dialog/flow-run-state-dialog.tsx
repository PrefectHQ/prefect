import type { FlowRun } from "@/api/flow-runs";
import { RunStateChangeDialog } from "@/components/ui/run-state-change-dialog";
import { useFlowRunStateDialog } from "./use-flow-run-state-dialog";

interface FlowRunStateDialogProps {
	flowRun: FlowRun | null;
}

export const FlowRunStateDialog = ({ flowRun }: FlowRunStateDialogProps) => {
	const { dialogProps } = useFlowRunStateDialog(flowRun);

	if (!dialogProps) {
		return null;
	}

	return <RunStateChangeDialog {...dialogProps} />;
};
