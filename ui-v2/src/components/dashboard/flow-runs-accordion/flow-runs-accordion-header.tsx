import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import {
	buildFilterFlowRunsQuery,
	type FlowRun,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { FlowIconText } from "@/components/flows/flow-icon-text";
import { FormattedDate } from "@/components/ui/formatted-date";

type FlowRunsAccordionHeaderProps = {
	/** The flow to display */
	flow: Flow;
	/** The filter used by the parent accordion to fetch flow runs */
	filter: FlowRunsFilter;
};

/**
 * Header component for each accordion section.
 * Displays flow name, last run time, and count of runs.
 *
 * Uses TanStack Query's `select` to derive per-flow count and last run
 * from the parent's already-cached flow runs query, avoiding N+1 queries.
 */
export function FlowRunsAccordionHeader({
	flow,
	filter,
}: FlowRunsAccordionHeaderProps) {
	const select = useCallback(
		(flowRuns: FlowRun[]) => {
			const forFlow = flowRuns.filter((r) => r.flow_id === flow.id);
			let lastRun: FlowRun | undefined;
			for (const run of forFlow) {
				if (
					!lastRun ||
					(run.start_time &&
						(!lastRun.start_time || run.start_time > lastRun.start_time))
				) {
					lastRun = run;
				}
			}
			return { count: forFlow.length, lastFlowRun: lastRun };
		},
		[flow.id],
	);

	const { data } = useQuery({
		...buildFilterFlowRunsQuery(filter, 30_000),
		select,
	});

	const count = data?.count ?? 0;
	const lastFlowRun = data?.lastFlowRun;

	return (
		<div className="flex w-full items-center justify-between gap-4 pr-2">
			<div className="flex flex-col items-start gap-1">
				<FlowIconText
					flow={flow}
					className="text-sm font-medium text-foreground hover:underline flex items-center gap-1"
					onClick={(e) => e.stopPropagation()}
				/>
				{lastFlowRun?.start_time && (
					<FormattedDate
						date={new Date(lastFlowRun.start_time)}
						format="relative"
						className="text-xs text-muted-foreground"
					/>
				)}
			</div>
			<span className="text-sm font-medium text-muted-foreground">{count}</span>
		</div>
	);
}
