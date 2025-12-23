import type { Flow } from "@/api/flows";
import { CumulativeTaskRunsCard } from "./cumulative-task-runs-card";
import { FlowRunsHistoryCard } from "./flow-runs-history-card";

type FlowStatsSummaryProps = {
	flowId: string;
	flow: Flow;
};

export function FlowStatsSummary({ flowId, flow }: FlowStatsSummaryProps) {
	return (
		<div className="grid gap-5 md:grid-cols-[2fr_1fr]">
			<FlowRunsHistoryCard flowId={flowId} flow={flow} />
			<CumulativeTaskRunsCard flowId={flowId} />
		</div>
	);
}
