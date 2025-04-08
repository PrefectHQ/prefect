import type { FlowRun } from "@/api/flow-runs";
import { RunStateChangeDialog } from "@/components/ui/run-state-change-dialog";
import { useFlowRunStateDialog } from "./use-flow-run-state-dialog";

type FlowRunStateDialogProps = {
	flowRun: FlowRun;
};

export const FlowRunStateDialog = ({ flowRun }: FlowRunStateDialogProps) => {
	const { dialogProps } = useFlowRunStateDialog(flowRun);

	return <RunStateChangeDialog {...dialogProps} />;
};
