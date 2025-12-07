import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { format, parseISO } from "date-fns";
import humanizeDuration from "humanize-duration";
import { useMemo, useState } from "react";
import {
	buildPaginateFlowRunsQuery,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationNext,
	PaginationPrevious,
} from "@/components/ui/pagination";
import { StateBadge } from "@/components/ui/state-badge";
import { Typography } from "@/components/ui/typography";

type FlowRunsAccordionContentProps = {
	/** The flow ID to display runs for */
	flowId: string;
	/** Filter for flow runs */
	filter?: FlowRunsFilter;
};

const ITEMS_PER_PAGE = 3;

/**
 * Content component for each accordion section.
 * Displays a paginated list of flow runs for a specific flow.
 */
export function FlowRunsAccordionContent({
	flowId,
	filter,
}: FlowRunsAccordionContentProps) {
	const [page, setPage] = useState(1);

	// Build filter for this specific flow with pagination
	const paginatedFilter = useMemo(() => {
		return {
			...filter,
			flows: {
				...filter?.flows,
				operator: "and_" as const,
				id: { any_: [flowId] },
			},
			page,
			limit: ITEMS_PER_PAGE,
			sort: "START_TIME_DESC" as const,
		};
	}, [filter, flowId, page]);

	// Fetch paginated flow runs
	const { data } = useQuery(
		buildPaginateFlowRunsQuery(paginatedFilter, 30_000),
	);

	const flowRuns = data?.results ?? [];
	const totalPages = data?.pages ?? 1;

	return (
		<div className="space-y-3">
			{flowRuns.map((flowRun) => (
				<div
					key={flowRun.id}
					className="flex flex-col gap-2 rounded-md border-l-4 bg-muted/30 p-3"
					style={{
						borderLeftColor: getStateColor(flowRun.state_type),
					}}
				>
					<div className="flex items-center justify-between">
						<Link
							to="/runs/flow-run/$id"
							params={{ id: flowRun.id }}
							className="text-sm font-medium text-foreground hover:underline"
						>
							{flowRun.name}
						</Link>
					</div>
					<div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
						{flowRun.state_type && (
							<StateBadge
								type={flowRun.state_type}
								name={flowRun.state_name}
								className="text-xs"
							/>
						)}
						{flowRun.start_time && (
							<div className="flex items-center gap-1">
								<Icon id="Calendar" className="size-3" />
								<span className="font-mono">
									{format(parseISO(flowRun.start_time), "yyyy/MM/dd pp")}
								</span>
							</div>
						)}
						{flowRun.estimated_run_time !== undefined && (
							<div className="flex items-center gap-1">
								<Icon id="Clock" className="size-3" />
								<span>
									{humanizeDuration(flowRun.estimated_run_time * 1000, {
										maxDecimalPoints: 0,
										units: ["h", "m", "s"],
										round: true,
									})}
								</span>
							</div>
						)}
						{flowRun.total_task_run_count !== undefined &&
							flowRun.total_task_run_count > 0 && (
								<div className="flex items-center gap-1">
									<Icon id="Layers" className="size-3" />
									<span>
										{flowRun.total_task_run_count} Task run
										{flowRun.total_task_run_count !== 1 ? "s" : ""}
									</span>
								</div>
							)}
					</div>
				</div>
			))}

			{totalPages > 1 && (
				<Pagination className="justify-start">
					<PaginationContent>
						<PaginationItem>
							<PaginationPrevious
								onClick={() => setPage((p) => Math.max(1, p - 1))}
								className={
									page === 1
										? "pointer-events-none opacity-50"
										: "cursor-pointer"
								}
							/>
						</PaginationItem>
						<PaginationItem>
							<Typography variant="bodySmall" className="px-2">
								Page {page} of {totalPages}
							</Typography>
						</PaginationItem>
						<PaginationItem>
							<PaginationNext
								onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
								className={
									page === totalPages
										? "pointer-events-none opacity-50"
										: "cursor-pointer"
								}
							/>
						</PaginationItem>
					</PaginationContent>
				</Pagination>
			)}
		</div>
	);
}

function getStateColor(stateType: string | null | undefined): string {
	switch (stateType) {
		case "COMPLETED":
			return "rgb(22 163 74)"; // green-600
		case "FAILED":
			return "rgb(220 38 38)"; // red-600
		case "RUNNING":
			return "rgb(29 78 216)"; // blue-700
		case "CANCELLED":
		case "CANCELLING":
		case "PAUSED":
		case "PENDING":
			return "rgb(31 41 55)"; // gray-800
		case "CRASHED":
			return "rgb(234 88 12)"; // orange-600
		case "SCHEDULED":
			return "rgb(161 98 7)"; // yellow-700
		default:
			return "rgb(107 114 128)"; // gray-500
	}
}
