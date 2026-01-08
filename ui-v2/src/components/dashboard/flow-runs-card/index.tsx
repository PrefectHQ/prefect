import { useQuery } from "@tanstack/react-query";
import { Suspense, useCallback, useMemo, useState } from "react";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { categorizeError } from "@/api/error-utils";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsFilter,
	toFlowRunsCountFilter,
} from "@/api/flow-runs";
import { buildListFlowsQuery } from "@/api/flows";
import type { components } from "@/api/prefect";
import { FlowRunsAccordion } from "@/components/dashboard/flow-runs-accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardErrorState } from "@/components/ui/card-error-state";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import { Skeleton } from "@/components/ui/skeleton";
import useDebounce from "@/hooks/use-debounce";
import { FlowRunsCardSkeleton } from "./flow-runs-card-skeleton";
import { FlowRunStateTabs, type StateTypeCounts } from "./flow-runs-state-tabs";

type StateType = components["schemas"]["StateType"];

type FlowRunsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
	selectedStates?: StateType[];
	onStateChange?: (states: StateType[]) => void;
};

const BAR_WIDTH = 8;
const BAR_GAP = 4;

export function FlowRunsCard({
	filter,
	selectedStates: controlledSelectedStates,
	onStateChange: controlledOnStateChange,
}: FlowRunsCardProps) {
	const [numberOfBars, setNumberOfBars] = useState<number>(0);
	const debouncedNumberOfBars = useDebounce(numberOfBars, 150);
	const [internalSelectedStates, setInternalSelectedStates] = useState<
		StateType[]
	>(["FAILED", "CRASHED"]);

	// Use controlled state if provided, otherwise use internal state
	const selectedStates = controlledSelectedStates ?? internalSelectedStates;
	const handleStateChange =
		controlledOnStateChange ?? setInternalSelectedStates;

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

	const flowRunsQuery = useQuery(
		buildFilterFlowRunsQuery(flowRunsFilter, 30000),
	);

	// Convert the filter to a count filter (without sort/limit/offset)
	const countFilter = useMemo(
		() => toFlowRunsCountFilter(flowRunsFilter),
		[flowRunsFilter],
	);

	// Fetch total count using the count API (not limited by default API limit)
	const totalCountQuery = useQuery(buildCountFlowRunsQuery(countFilter, 30000));

	// Fetch counts for each state type group using the count API
	const failedCrashedQuery = useQuery(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["FAILED", "CRASHED"] } },
				},
			},
			30000,
		),
	);

	const runningPendingCancellingQuery = useQuery(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: {
						operator: "and_",
						type: { any_: ["RUNNING", "PENDING", "CANCELLING"] },
					},
				},
			},
			30000,
		),
	);

	const completedQuery = useQuery(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["COMPLETED"] } },
				},
			},
			30000,
		),
	);

	const scheduledPausedQuery = useQuery(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["SCHEDULED", "PAUSED"] } },
				},
			},
			30000,
		),
	);

	const cancelledQuery = useQuery(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["CANCELLED"] } },
				},
			},
			30000,
		),
	);

	// Extract data from queries with defaults
	const allFlowRuns = flowRunsQuery.data ?? [];
	const totalCount = totalCountQuery.data ?? 0;
	const failedCrashedCount = failedCrashedQuery.data ?? 0;
	const runningPendingCancellingCount = runningPendingCancellingQuery.data ?? 0;
	const completedCount = completedQuery.data ?? 0;
	const scheduledPausedCount = scheduledPausedQuery.data ?? 0;
	const cancelledCount = cancelledQuery.data ?? 0;

	// Build state counts object for FlowRunStateTabs
	// Note: We distribute counts evenly among grouped states for display purposes
	// The actual count shown in the tab is the sum of all states in the group
	const stateCounts: StateTypeCounts = useMemo(
		() => ({
			FAILED: failedCrashedCount,
			CRASHED: 0, // Grouped with FAILED
			RUNNING: runningPendingCancellingCount,
			PENDING: 0, // Grouped with RUNNING
			CANCELLING: 0, // Grouped with RUNNING
			COMPLETED: completedCount,
			SCHEDULED: scheduledPausedCount,
			PAUSED: 0, // Grouped with SCHEDULED
			CANCELLED: cancelledCount,
		}),
		[
			failedCrashedCount,
			runningPendingCancellingCount,
			completedCount,
			scheduledPausedCount,
			cancelledCount,
		],
	);

	// Extract unique flow and deployment IDs from all flow runs for enrichment
	const { flowIds, deploymentIds } = useMemo(() => {
		const flowIds = [...new Set(allFlowRuns.map((fr) => fr.flow_id))];
		const deploymentIds = [
			...new Set(
				allFlowRuns
					.map((fr) => fr.deployment_id)
					.filter((id): id is string => !!id),
			),
		];
		return { flowIds, deploymentIds };
	}, [allFlowRuns]);

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
		return allFlowRuns.map((flowRun) => {
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
	}, [allFlowRuns, flows, deployments]);

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

	// Combine all query errors - if any critical query fails, show error
	const criticalQueries = [
		flowRunsQuery,
		totalCountQuery,
		failedCrashedQuery,
		runningPendingCancellingQuery,
		completedQuery,
		scheduledPausedQuery,
		cancelledQuery,
	];

	const failedQuery = criticalQueries.find((q) => q.isError);
	if (failedQuery) {
		return (
			<CardErrorState
				error={categorizeError(failedQuery.error, "Failed to load flow runs")}
				onRetry={() => {
					// Refetch all failed queries
					criticalQueries
						.filter((q) => q.isError)
						.forEach((q) => void q.refetch());
				}}
				isRetrying={criticalQueries.some((q) => q.isRefetching)}
			/>
		);
	}

	// Show loading state while critical data is loading
	const isCriticalLoading = criticalQueries.some((q) => q.isLoading);
	if (isCriticalLoading) {
		return <FlowRunsCardSkeleton />;
	}

	// Only show loading state if we have flow runs to enrich
	const hasFlowRuns = allFlowRuns.length > 0;
	const isLoadingEnrichment =
		hasFlowRuns &&
		((isLoadingFlows && flowIds.length > 0) ||
			(isLoadingDeployments && deploymentIds.length > 0));

	// Use debounced value if available, otherwise use immediate value
	// This prevents showing empty chart on initial render while still being responsive
	const effectiveNumberOfBars = debouncedNumberOfBars || numberOfBars;

	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle>Flow Runs</CardTitle>
				{totalCount > 0 && (
					<span className="text-sm text-muted-foreground">
						{totalCount} total
					</span>
				)}
			</CardHeader>
			<CardContent className="space-y-2">
				{isLoadingEnrichment || effectiveNumberOfBars === 0 ? (
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
							stateCounts={stateCounts}
							selectedStates={selectedStates}
							onStateChange={handleStateChange}
						/>
						<Suspense fallback={<Skeleton className="h-32 w-full" />}>
							<FlowRunsAccordion
								filter={flowRunsFilter}
								stateTypes={selectedStates}
							/>
						</Suspense>
					</>
				)}
			</CardContent>
		</Card>
	);
}
