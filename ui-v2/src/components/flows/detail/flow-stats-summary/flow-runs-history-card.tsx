import { useSuspenseQueries } from "@tanstack/react-query";
import { subDays } from "date-fns";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRun,
} from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	FlowRunActivityBarChart,
	FlowRunActivityBarGraphTooltipProvider,
} from "@/components/ui/flow-run-activity-bar-graph";
import { Skeleton } from "@/components/ui/skeleton";
import useDebounce from "@/hooks/use-debounce";
import {
	buildFlowRunsCountFilterForHistory,
	buildFlowRunsHistoryFilter,
} from "./query-filters";

const BAR_WIDTH = 8;
const BAR_GAP = 4;
const REFETCH_INTERVAL = 30_000;

type FlowRunsHistoryCardProps = {
	flowId: string;
	flow: Flow;
};

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
	// Use a fixed limit of 60 to ensure query key stability with prefetch
	const QUERY_LIMIT = 60;

	const [{ data: flowRuns }, { data: totalCount }] = useSuspenseQueries({
		queries: [
			buildFilterFlowRunsQuery(
				buildFlowRunsHistoryFilter(flowId, QUERY_LIMIT),
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
