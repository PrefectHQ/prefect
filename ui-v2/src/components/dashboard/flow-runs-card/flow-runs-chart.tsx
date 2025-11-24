import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import useDebounce from "@/hooks/use-debounce";

const BAR_WIDTH = 8;
const BAR_GAP = 4;

type EnrichedFlowRun = components["schemas"]["FlowRunResponse"] & {
	deployment: components["schemas"]["DeploymentResponse"];
	flow?: components["schemas"]["Flow"];
};

type FlowRunsChartProps = {
	flowRuns: FlowRun[];
	dateRange: { start: Date; end: Date };
};

export function FlowRunsChart({ flowRuns, dateRange }: FlowRunsChartProps) {
	const [numberOfBars, setNumberOfBars] = useState<number>(0);
	const debouncedNumberOfBars = useDebounce(numberOfBars, 150);

	const chartRef = useCallback((node: HTMLDivElement | null) => {
		if (!node) return;

		const updateBars = () => {
			const chartWidth = node.getBoundingClientRect().width;
			setNumberOfBars(Math.floor(chartWidth / (BAR_WIDTH + BAR_GAP)));
		};

		// Set the initial number of bars based on the chart width
		updateBars();

		// Observe the chart for resize events
		const resizeObserver = new ResizeObserver(updateBars);
		resizeObserver.observe(node);
		return () => {
			// Clean up the observer
			resizeObserver.disconnect();
		};
	}, []);

	// Extract unique flow IDs from flow runs
	const flowIds = useMemo(() => {
		if (!flowRuns) {
			return [];
		}
		return Array.from(new Set(flowRuns.map((flowRun) => flowRun.flow_id)));
	}, [flowRuns]);

	// Extract unique deployment IDs from flow runs (filter out null/undefined)
	const deploymentIds = useMemo(() => {
		if (!flowRuns) {
			return [];
		}
		return Array.from(
			new Set(
				flowRuns
					.map((flowRun) => flowRun.deployment_id)
					.filter((id): id is string => id != null),
			),
		);
	}, [flowRuns]);

	// Fetch flows
	const { data: flows } = useQuery(
		buildListFlowsQuery(
			{
				flows: { id: { any_: flowIds }, operator: "and_" },
				offset: 0,
				sort: "CREATED_DESC",
			},
			{ enabled: flowIds.length > 0 },
		),
	);

	// Fetch deployments
	const { data: deployments } = useQuery(
		buildFilterDeploymentsQuery(
			{
				deployments: { id: { any_: deploymentIds }, operator: "and_" },
				offset: 0,
				sort: "CREATED_DESC",
			},
			{ enabled: deploymentIds.length > 0 },
		),
	);

	// Create maps for efficient lookup
	const flowMap = useMemo(() => {
		if (!flows) {
			return new Map<string, Flow>();
		}
		return new Map(flows.map((flow) => [flow.id, flow]));
	}, [flows]);

	const deploymentMap = useMemo(() => {
		if (!deployments) {
			return new Map<string, components["schemas"]["DeploymentResponse"]>();
		}
		return new Map(
			deployments.map((deployment) => [deployment.id, deployment]),
		);
	}, [deployments]);

	// Enrich flow runs with deployment and flow data
	const enrichedFlowRuns: EnrichedFlowRun[] = useMemo(() => {
		if (!flowRuns) {
			return [];
		}

		const enriched: EnrichedFlowRun[] = [];

		for (const flowRun of flowRuns) {
			if (flowRun.deployment_id == null) {
				continue;
			}

			const flow = flowMap.get(flowRun.flow_id);
			const deployment = deploymentMap.get(flowRun.deployment_id);

			// Only include flow runs that have a deployment
			// (required by EnrichedFlowRun type)
			if (!deployment) {
				continue;
			}

			enriched.push({
				...flowRun,
				deployment,
				flow,
			});
		}

		return enriched;
	}, [flowRuns, flowMap, deploymentMap]);

	return (
		<div className="w-full" ref={chartRef}>
			<FlowRunActivityBarChart
				startDate={dateRange.start}
				endDate={dateRange.end}
				// If debouncedNumberOfBars is 0, use numberOfBars for an asymmetric debounce to avoid rendering an empty chart on initial paint.
				numberOfBars={debouncedNumberOfBars || numberOfBars}
				barWidth={BAR_WIDTH}
				enrichedFlowRuns={enrichedFlowRuns}
				className="h-12 w-full"
			/>
		</div>
	);
}
