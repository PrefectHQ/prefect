import type { Flow } from "@/api/flows";
import { CumulativeTaskRunsCard } from "./cumulative-task-runs-card";
import { FlowRunsHistoryCard } from "./flow-runs-history-card";

type FlowStatsSummaryProps = {
	flowId: string;
	flow: Flow;
};

export function FlowStatsSummary({ flowId, flow }: FlowStatsSummaryProps) {
	return (
		<div className="flex gap-4 mb-4">
			<FlowRunsHistoryCard flowId={flowId} flow={flow} />
			<CumulativeTaskRunsCard flowId={flowId} />
		</div>
	);
}

export {
	buildCompletedTaskRunsCountFilter,
	buildFailedTaskRunsCountFilter,
	buildRunningTaskRunsCountFilter,
	buildTaskRunsHistoryFilterForFlow,
	buildTotalTaskRunsCountFilter,
	CumulativeTaskRunsCard,
} from "./cumulative-task-runs-card";
export {
	buildFlowRunsCountFilterForHistory,
	buildFlowRunsHistoryFilter,
	FlowRunsHistoryCard,
} from "./flow-runs-history-card";
