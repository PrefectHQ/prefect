import { useSuspenseQuery } from "@tanstack/react-query";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { FlowRunsList } from "@/components/flow-runs/flow-runs-list";

type WorkPoolFlowRunsTabProps = {
	workPoolName: string;
	className?: string;
};

export const WorkPoolFlowRunsTab = ({
	workPoolName,
	className,
}: WorkPoolFlowRunsTabProps) => {
	const { data: flowRuns } = useSuspenseQuery(
		buildFilterFlowRunsQuery({
			work_pools: {
				operator: "and_",
				name: { any_: [workPoolName] },
			},
			limit: 100,
			offset: 0,
			sort: "START_TIME_DESC",
		}),
	);

	return (
		<div className={className}>
			<FlowRunsList flowRuns={flowRuns} />
		</div>
	);
};
