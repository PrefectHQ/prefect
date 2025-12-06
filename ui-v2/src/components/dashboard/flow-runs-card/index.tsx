import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { buildFilterFlowRunsQuery, type FlowRunsFilter } from "@/api/flow-runs";
import { buildListFlowsQuery } from "@/api/flows";
import type { components } from "@/api/prefect";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import { Skeleton } from "@/components/ui/skeleton";
import useDebounce from "@/hooks/use-debounce";
import { FlowRunStateTabs } from "./flow-runs-state-tabs";

type StateType = components["schemas"]["StateType"];

type FlowRunsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
};

const BAR_WIDTH = 8;
const BAR_GAP = 4;

export function FlowRunsCard({ filter }: FlowRunsCardProps) {
	const [numberOfBars, setNumberOfBars] = useState<number>(0);
	const debouncedNumberOfBars = useDebounce(numberOfBars, 150);
	const [selectedState, setSelectedState] = useState<StateType>("FAILED");

	const chartRef = useCallback((node: HTMLDivElement | null) => {
		if (!node) return;

		const updateBars = () => {
			const chartWidth = node.getBoundingClientRect().width;
			setNumberOfBars(Math.floor(chartWidth / (BAR_WIDTH + BAR_GAP)));
		};

		updateBars();
		const resizeObserver = new ResizeObserver(updateBars);
		resizeObserver.observe(node);
		return () => resizeObserver.disconnect();
	}, []);

	const flowRunsFilter: FlowRunsFilter = useMemo(() => {
		const baseFilter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};

		const flowRunsFilterObj: NonNullable<FlowRunsFilter["flow_runs"]> = {
			operator: "and_",
		};

		if (filter?.startDate && filter?.endDate) {
			flowRunsFilterObj.start_time = {
				after_: filter.startDate,
				before_: filter.endDate,
			};
		}

		if (filter?.tags && filter.tags.length > 0) {
			flowRunsFilterObj.tags = {
				operator: "and_",
				all_: filter.tags,
			};
		}

		if (filter?.hideSubflows) {
			flowRunsFilterObj.parent_task_run_id = {
				operator: "and_",
				is_null_: true,
			};
		}

		if (Object.keys(flowRunsFilterObj).length > 1) {
			baseFilter.flow_runs = flowRunsFilterObj;
		}

		return baseFilter;
	}, [filter?.startDate, filter?.endDate, filter?.tags, filter?.hideSubflows]);

	const { data: allFlowRuns } = useSuspenseQuery(
		buildFilterFlowRunsQuery(flowRunsFilter, 30000),
	);

	// Filter flow runs by selected state for display
	const flowRuns = useMemo(() => {
		return allFlowRuns.filter((run) => run.state_type === selectedState);
	}, [allFlowRuns, selectedState]);

	// Extract unique flow and deployment IDs from flow runs
	const { flowIds, deploymentIds } = useMemo(() => {
		const flowIds = [...new Set(flowRuns.map((fr) => fr.flow_id))];
		const deploymentIds = [
			...new Set(
				flowRuns
					.map((fr) => fr.deployment_id)
					.filter((id): id is string => !!id),
			),
		];
		return { flowIds, deploymentIds };
	}, [flowRuns]);

	// Fetch flows for enrichment
	const { data: flows, isLoading: isLoadingFlows } = useQuery(
		buildListFlowsQuery(
			{
				flows: { operator: "and_", id: { any_: flowIds } },
				offset: 0,
				sort: "CREATED_DESC",
			},
			{ enabled: flowIds.length > 0 },
		),
	);

	// Fetch deployments for enrichment
	const { data: deployments, isLoading: isLoadingDeployments } = useQuery(
		buildFilterDeploymentsQuery(
			{
				deployments: { operator: "and_", id: { any_: deploymentIds } },
				offset: 0,
				sort: "CREATED_DESC",
			},
			{ enabled: deploymentIds.length > 0 },
		),
	);

	// Enrich flow runs with flow and deployment data
	const enrichedFlowRuns = useMemo(() => {
		return flowRuns.map((flowRun) => {
			const flow = flows?.find((f) => f.id === flowRun.flow_id);
			const deployment = deployments?.find(
				(d) => d.id === flowRun.deployment_id,
			);
			return {
				...flowRun,
				flow,
				deployment,
			};
		});
	}, [flowRuns, flows, deployments]);

	// Calculate date range from filter or default to last 7 days
	const { startDate, endDate } = useMemo(() => {
		if (filter?.startDate && filter?.endDate) {
			return {
				startDate: new Date(filter.startDate),
				endDate: new Date(filter.endDate),
			};
		}

		// Default to last 7 days
		const end = new Date();
		const start = new Date();
		start.setDate(start.getDate() - 7);

		return { startDate: start, endDate: end };
	}, [filter?.startDate, filter?.endDate]);

	const isLoadingEnrichment =
		(isLoadingFlows && flowIds.length > 0) ||
		(isLoadingDeployments && deploymentIds.length > 0);

	// Use debounced value if available, otherwise use immediate value
	// This prevents showing empty chart on initial render while still being responsive
	const effectiveNumberOfBars = debouncedNumberOfBars || numberOfBars;

	// Count failed or crashed runs for the message display
	const failedOrCrashedCount = useMemo(() => {
		return allFlowRuns.filter(
			(run) => run.state_type === "FAILED" || run.state_type === "CRASHED",
		).length;
	}, [allFlowRuns]);

	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle>Flow Runs</CardTitle>
				{allFlowRuns.length > 0 && (
					<span className="text-sm text-muted-foreground">
						{allFlowRuns.length} total
					</span>
				)}
			</CardHeader>
			<CardContent className="space-y-2">
				{allFlowRuns.length === 0 ? (
					<div className="my-8 text-center text-sm text-muted-foreground">
						<p>No flow runs found</p>
					</div>
				) : isLoadingEnrichment || effectiveNumberOfBars === 0 ? (
					<div className="w-full" ref={chartRef}>
						<Skeleton className="h-24 w-full" />
					</div>
				) : (
					<>
						<div className="w-full" ref={chartRef}>
							<FlowRunActivityBarChart
								enrichedFlowRuns={enrichedFlowRuns}
								startDate={startDate}
								endDate={endDate}
								numberOfBars={effectiveNumberOfBars}
								barWidth={BAR_WIDTH}
								className="h-24 w-full"
							/>
						</div>
						<FlowRunStateTabs
							flowRuns={allFlowRuns}
							selectedState={selectedState}
							onStateChange={setSelectedState}
							failedOrCrashedCount={failedOrCrashedCount}
						/>
					</>
				)}
			</CardContent>
		</Card>
	);
}
