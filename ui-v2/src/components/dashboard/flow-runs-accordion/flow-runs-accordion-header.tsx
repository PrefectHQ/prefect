import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { FlowIconText } from "@/components/flows/flow-icon-text";
import { FormattedDate } from "@/components/ui/formatted-date";

type FlowRunsAccordionHeaderProps = {
	/** The flow to display */
	flow: Flow;
	/** Filter for flow runs */
	filter: FlowRunsFilter;
};

/**
 * Header component for each accordion section.
 * Displays flow name, last run time, and count of runs.
 */
export function FlowRunsAccordionHeader({
	flow,
	filter,
}: FlowRunsAccordionHeaderProps) {
	// Build filter for this specific flow
	const flowFilter: FlowRunsFilter = useMemo(() => {
		return {
			...filter,
			flows: {
				...(filter.flows ?? {}),
				operator: "and_",
				id: { any_: [flow.id] },
			},
		};
	}, [filter, flow.id]);

	// Fetch count of flow runs for this flow
	const { data: count } = useQuery(buildCountFlowRunsQuery(flowFilter, 30_000));

	// Fetch last flow run for this flow
	const lastFlowRunFilter: FlowRunsFilter = useMemo(() => {
		return {
			...flowFilter,
			sort: "START_TIME_DESC",
			limit: 1,
			offset: 0,
		};
	}, [flowFilter]);

	const { data: lastFlowRuns } = useQuery(
		buildFilterFlowRunsQuery(lastFlowRunFilter, 30_000),
	);

	const lastFlowRun = lastFlowRuns?.[0];

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
			<span className="text-sm font-medium text-muted-foreground">
				{count ?? 0}
			</span>
		</div>
	);
}
