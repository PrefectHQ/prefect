import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildFilterFlowRunsQuery, type FlowRunsFilter } from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow, type FlowsFilter } from "@/api/flows";
import type { components } from "@/api/prefect";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowRunStateTypeEmpty } from "./flow-run-state-type-empty";
import { FlowRunsAccordionContent } from "./flow-runs-accordion-content";
import { FlowRunsAccordionHeader } from "./flow-runs-accordion-header";

type StateType = components["schemas"]["StateType"];

export type FlowRunsAccordionProps = {
	/** Filter for flow runs */
	filter?: FlowRunsFilter;
	/** State types to filter by */
	stateTypes: StateType[];
	/**
	 * Flow ID whose pagination is currently persisted (e.g. in the URL).
	 * The `page` prop is only applied to the section matching this id; all
	 * other sections default to page 1. This mirrors V1 behavior where
	 * pagination is scoped to a single (state, flow) pair at a time.
	 */
	activeFlowId?: string;
	/** Controlled page value for the section matching `activeFlowId`. */
	page?: number;
	/**
	 * Called when the user navigates to a different page inside one of the
	 * accordion sections. Receives the flow id so callers can scope the
	 * persisted page to a specific flow.
	 */
	onPageChange?: (flowId: string, page: number) => void;
};

/**
 * Accordion component that displays flow runs grouped by flow.
 * Each accordion section shows a flow with its runs.
 */
export function FlowRunsAccordion({
	filter,
	stateTypes,
	activeFlowId,
	page,
	onPageChange,
}: FlowRunsAccordionProps) {
	// Build the flow runs filter with state type
	const flowRunsFilter: FlowRunsFilter = useMemo(() => {
		const baseFilter: FlowRunsFilter = {
			sort: "EXPECTED_START_TIME_DESC",
			offset: 0,
			...filter,
		};

		// Add state type filter
		if (stateTypes.length > 0) {
			baseFilter.flow_runs = {
				...baseFilter.flow_runs,
				operator: "and_",
				state: {
					operator: "and_",
					type: {
						any_: stateTypes,
					},
				},
			};
		}

		return baseFilter;
	}, [filter, stateTypes]);

	// Fetch flow runs for the selected state type tab
	const { data: flowRuns, isLoading } = useQuery(
		buildFilterFlowRunsQuery(flowRunsFilter, 30_000),
	);

	// Extract unique flow IDs from flow runs
	const flowIds = useMemo(() => {
		if (!flowRuns) return [];
		return [...new Set(flowRuns.map((fr) => fr.flow_id))];
	}, [flowRuns]);

	// Build flows filter to fetch flows that have runs
	const flowsFilter: FlowsFilter = useMemo(() => {
		if (flowIds.length === 0) {
			return { offset: 0, sort: "UPDATED_DESC" };
		}
		return {
			flows: {
				operator: "and_",
				id: { any_: flowIds },
			},
			offset: 0,
			sort: "UPDATED_DESC",
		};
	}, [flowIds]);

	// Fetch flows
	const { data: flows, isLoading: isLoadingFlows } = useQuery(
		buildListFlowsQuery(flowsFilter, { enabled: flowIds.length > 0 }),
	);

	// Create a lookup map for flows
	const flowsLookup = useMemo(() => {
		const map = new Map<string, Flow>();
		if (flows) {
			for (const flow of flows) {
				map.set(flow.id, flow);
			}
		}
		return map;
	}, [flows]);

	// Show loading skeleton while fetching flow runs
	if (isLoading) {
		return <Skeleton className="h-32 w-full" />;
	}

	// Show empty state if no flow runs
	if (!flowRuns || flowRuns.length === 0) {
		return <FlowRunStateTypeEmpty stateTypes={stateTypes} />;
	}

	// Show loading state while flows are loading
	if (isLoadingFlows && flowIds.length > 0) {
		return null;
	}

	return (
		<Accordion type="multiple" className="w-full">
			{flowIds.map((flowId) => {
				const flow = flowsLookup.get(flowId);
				if (!flow) return null;

				const isActiveFlow = flowId === activeFlowId;
				// Only the section matching `activeFlowId` is controlled from props;
				// other sections manage their own page state internally.
				const sectionPage = isActiveFlow ? page : undefined;
				const sectionOnPageChange = onPageChange
					? (next: number) => onPageChange(flowId, next)
					: undefined;

				return (
					<AccordionItem key={flowId} value={flowId}>
						<AccordionTrigger className="hover:no-underline">
							<FlowRunsAccordionHeader flow={flow} filter={flowRunsFilter} />
						</AccordionTrigger>
						<AccordionContent>
							<FlowRunsAccordionContent
								flowId={flowId}
								filter={flowRunsFilter}
								page={sectionPage}
								onPageChange={sectionOnPageChange}
							/>
						</AccordionContent>
					</AccordionItem>
				);
			})}
		</Accordion>
	);
}
