import { useQuery } from "@tanstack/react-query";
import { subSeconds } from "date-fns";
import { secondsInWeek } from "date-fns/constants";
import { useCallback, useState } from "react";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import useDebounce from "@/hooks/use-debounce";

const BAR_WIDTH = 4;
const BAR_GAP = 2;

interface MiniDeploymentActivityProps {
	deploymentId: string;
}

export const MiniDeploymentActivity = ({
	deploymentId,
}: MiniDeploymentActivityProps) => {
	const [numberOfBars, setNumberOfBars] = useState<number>(0);
	const debouncedNumberOfBars = useDebounce(numberOfBars, 150);

	const chartRef = useCallback((node: HTMLDivElement | null) => {
		if (!node) return;

		const updateBars = () => {
			const chartWidth = node.getBoundingClientRect().width;
			setNumberOfBars(Math.floor(chartWidth / (BAR_WIDTH + BAR_GAP)));
		};

		updateBars();

		const resizeObserver = new ResizeObserver(updateBars);
		resizeObserver.observe(node);
		return () => {
			resizeObserver.disconnect();
		};
	}, []);

	const effectiveNumberOfBars = debouncedNumberOfBars || numberOfBars;

	const { data: flowRuns } = useQuery(
		buildFilterFlowRunsQuery({
			deployments: {
				operator: "and_",
				id: { any_: [deploymentId] },
			},
			limit: Math.min(60, effectiveNumberOfBars || 60),
			sort: "START_TIME_DESC",
			offset: 0,
		}),
	);

	const enrichedFlowRuns =
		flowRuns?.map((flowRun) => ({
			...flowRun,
		})) ?? [];

	return (
		<div className="w-full" ref={chartRef}>
			<FlowRunActivityBarChart
				enrichedFlowRuns={enrichedFlowRuns}
				startDate={subSeconds(new Date(), secondsInWeek)}
				endDate={new Date()}
				barWidth={BAR_WIDTH}
				numberOfBars={effectiveNumberOfBars}
				className="h-8 w-full"
				chartId={`deployment-${deploymentId}`}
			/>
		</div>
	);
};
