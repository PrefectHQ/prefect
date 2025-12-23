import { useQuery } from "@tanstack/react-query";
import { subSeconds } from "date-fns";
import { secondsInWeek } from "date-fns/constants";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";

const BAR_WIDTH = 4;
const NUMBER_OF_BARS = 15;

interface MiniDeploymentActivityProps {
	deploymentId: string;
}

export const MiniDeploymentActivity = ({
	deploymentId,
}: MiniDeploymentActivityProps) => {
	const { data: flowRuns } = useQuery(
		buildFilterFlowRunsQuery({
			deployments: {
				operator: "and_",
				id: { any_: [deploymentId] },
			},
			limit: 60,
			sort: "START_TIME_DESC",
			offset: 0,
		}),
	);

	const enrichedFlowRuns =
		flowRuns?.map((flowRun) => ({
			...flowRun,
		})) ?? [];

	return (
		<FlowRunActivityBarChart
			enrichedFlowRuns={enrichedFlowRuns}
			startDate={subSeconds(new Date(), secondsInWeek)}
			endDate={new Date()}
			barWidth={BAR_WIDTH}
			numberOfBars={NUMBER_OF_BARS}
			className="h-8 w-full"
			chartId={`deployment-${deploymentId}`}
		/>
	);
};
