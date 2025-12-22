import { useSuspenseQueries } from "@tanstack/react-query";
import { subDays } from "date-fns";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRun,
	type FlowRunsCountFilter,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	FlowRunActivityBarChart,
	FlowRunActivityBarGraphTooltipProvider,
} from "@/components/ui/flow-run-activity-bar-graph";
import { Skeleton } from "@/components/ui/skeleton";
import useDebounce from "@/hooks/use-debounce";

const BAR_WIDTH = 8;
const BAR_GAP = 4;
const REFETCH_INTERVAL = 30_000;

type FlowRunsHistoryCardProps = {
	flowId: string;
	flow: Flow;
};

/**
 * Builds the filter for fetching flow runs for the history card.
 * Uses a stable date range (7 days ago to now) computed inside queryFn
 * to avoid query key instability with Suspense.
 */
export function buildFlowRunsHistoryFilter(
	flowId: string,
	limit: number,
): FlowRunsFilter {
	return {
		flows: { operator: "and_", id: { any_: [flowId] } },
		flow_runs: {
			operator: "and_",
			start_time: { is_null_: false },
		},
		offset: 0,
		limit,
		sort: "START_TIME_DESC",
	};
}

/**
 * Builds the filter for counting flow runs in the past 7 days.
 */
export function buildFlowRunsCountFilterForHistory(
	flowId: string,
): FlowRunsCountFilter {
	return {
		flows: { operator: "and_", id: { any_: [flowId] } },
		flow_runs: {
			operator: "and_",
			start_time: { is_null_: false },
		},
	};
}

export function FlowRunsHistoryCard({
	flowId,
	flow,
}: FlowRunsHistoryCardProps) {
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
		return () => resizeObserver.disconnect();
	}, []);

	const effectiveNumberOfBars = debouncedNumberOfBars || numberOfBars;
	const queryLimit = Math.max(effectiveNumberOfBars, 60);

	const [{ data: flowRuns }, { data: totalCount }] = useSuspenseQueries({
		queries: [
			buildFilterFlowRunsQuery(
				buildFlowRunsHistoryFilter(flowId, queryLimit),
				REFETCH_INTERVAL,
			),
			buildCountFlowRunsQuery(
				buildFlowRunsCountFilterForHistory(flowId),
				REFETCH_INTERVAL,
			),
		],
	});

	const enrichedFlowRuns = useMemo(
		() =>
			flowRuns.map((flowRun: FlowRun) => ({
				...flowRun,
				flow,
			})),
		[flowRuns, flow],
	);

	const { startDate, endDate } = useMemo((): {
		startDate: Date;
		endDate: Date;
	} => {
		const now = new Date();
		return {
			startDate: subDays(now, 7),
			endDate: now,
		};
	}, []);

	return (
		<Card className="flex-1">
			<CardHeader className="flex flex-row items-center justify-between pb-2">
				<CardTitle>Flow Runs</CardTitle>
				<span className="text-sm text-muted-foreground">
					{totalCount} total
				</span>
			</CardHeader>
			<CardContent>
				<div className="h-24" ref={chartRef}>
					{effectiveNumberOfBars === 0 ? (
						<Skeleton className="h-full w-full" />
					) : (
						<FlowRunActivityBarGraphTooltipProvider>
							<FlowRunActivityBarChart
								enrichedFlowRuns={enrichedFlowRuns}
								startDate={startDate}
								endDate={endDate}
								numberOfBars={effectiveNumberOfBars}
								barWidth={BAR_WIDTH}
								className="h-full w-full"
							/>
						</FlowRunActivityBarGraphTooltipProvider>
					)}
				</div>
			</CardContent>
		</Card>
	);
}
