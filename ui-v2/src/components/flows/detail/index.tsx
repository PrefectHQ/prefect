import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { subWeeks } from "date-fns";
import { type JSX, useCallback, useMemo, useState } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import {
	FlowRunsList,
	FlowRunsPagination,
	FlowRunsRowCount,
	type PaginationState,
	type SortFilters,
} from "@/components/flow-runs/flow-runs-list";
import { SortFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/sort-filter";
import { StateFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import { DataTable } from "@/components/ui/data-table";
import {
	FlowRunActivityBarChart,
	FlowRunActivityBarGraphTooltipProvider,
} from "@/components/ui/flow-run-activity-bar-graph";
import { SearchInput } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import useDebounce from "@/hooks/use-debounce";
import { DeleteFlowDialog } from "./delete-flow-dialog";
import { columns as deploymentColumns } from "./deployment-columns";
import { FlowPageHeader } from "./flow-page-header";
import {
	getFlowMetadata,
	columns as metadataColumns,
} from "./metadata-columns";

const BAR_WIDTH = 8;
const BAR_GAP = 4;

export default function FlowDetail({
	flow,
	flowRuns,
	flowRunsCount,
	flowRunsPages,
	activity,
	deployments,
	tab = "runs",
	pagination,
	onPaginationChange,
	onPrefetchPage,
	sort,
	onSortChange,
	flowRunSearch,
	onFlowRunSearchChange,
	selectedStates,
	onSelectFilter,
}: {
	flow: Flow;
	flowRuns: FlowRun[];
	flowRunsCount: number;
	flowRunsPages: number;
	activity: FlowRun[];
	deployments: components["schemas"]["DeploymentResponse"][];
	tab: "runs" | "deployments" | "details";
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onPrefetchPage: (page: number) => void;
	sort: SortFilters;
	onSortChange: (sort: SortFilters) => void;
	flowRunSearch: string | undefined;
	onFlowRunSearchChange: (search: string) => void;
	selectedStates: Set<FlowRunState>;
	onSelectFilter: (states: Set<FlowRunState>) => void;
}): JSX.Element {
	const navigate = useNavigate();
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
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

	const deploymentsTable = useReactTable({
		data: deployments,
		columns: deploymentColumns,
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		initialState: {
			pagination: {
				pageIndex: 0,
				pageSize: 10,
			},
		},
	});

	const metadataTable = useReactTable({
		columns: metadataColumns,
		data: getFlowMetadata(flow),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		onPaginationChange: (pagination) => {
			console.log(pagination);
			return pagination;
		},
		initialState: {
			pagination: {
				pageIndex: 0,
				pageSize: 10,
			},
		},
	});

	// Enrich activity flow runs with flow object for the chart
	const enrichedActivityFlowRuns = activity.map((flowRun) => ({
		...flowRun,
		flow: flow,
	}));

	// Enrich paginated flow runs with flow object for the list
	const enrichedFlowRuns: FlowRunCardData[] = flowRuns.map((flowRun) => ({
		...flowRun,
		flow: flow,
	}));

	// Handler to clear filters
	const onClearFilters = useCallback(() => {
		onFlowRunSearchChange("");
		onSelectFilter(new Set());
	}, [onFlowRunSearchChange, onSelectFilter]);

	// Calculate date range for the chart (last 7 days)
	const { startDate, endDate } = useMemo((): {
		startDate: Date;
		endDate: Date;
	} => {
		const now = new Date();
		return {
			startDate: subWeeks(now, 1),
			endDate: now,
		};
	}, []);

	// Use debounced value if available, otherwise use immediate value
	const effectiveNumberOfBars = debouncedNumberOfBars || numberOfBars;

	return (
		<>
			<div className="container mx-auto">
				<FlowPageHeader
					flow={flow}
					onDelete={() => setShowDeleteDialog(true)}
				/>
				<div className="mb-2 w-full" ref={chartRef}>
					{effectiveNumberOfBars === 0 ? (
						<Skeleton className="h-48 w-full" />
					) : (
						<FlowRunActivityBarGraphTooltipProvider>
							<FlowRunActivityBarChart
								enrichedFlowRuns={enrichedActivityFlowRuns}
								startDate={startDate}
								endDate={endDate}
								numberOfBars={effectiveNumberOfBars}
								barWidth={BAR_WIDTH}
								className="h-48 w-full"
							/>
						</FlowRunActivityBarGraphTooltipProvider>
					)}
				</div>
				<Tabs
					value={tab}
					onValueChange={(value) =>
						void navigate({
							to: ".",
							search: (prev) => ({
								...prev,
								tab: value as "runs" | "deployments" | "details",
							}),
						})
					}
				>
					<TabsList>
						<TabsTrigger value="runs">Runs</TabsTrigger>
						<TabsTrigger value="deployments">Deployments</TabsTrigger>
						<TabsTrigger value="details">Details</TabsTrigger>
					</TabsList>
					<TabsContent value="runs">
						<header className="mb-2 flex flex-row justify-between">
							<SearchInput
								placeholder="Run names"
								value={flowRunSearch ?? ""}
								onChange={(e) => onFlowRunSearchChange(e.target.value)}
							/>
							<div className="flex space-x-4">
								<StateFilter
									selectedFilters={selectedStates}
									onSelectFilter={onSelectFilter}
								/>
								<SortFilter value={sort} onSelect={onSortChange} />
							</div>
						</header>
						<FlowRunsRowCount count={flowRunsCount} />
						<FlowRunsList
							flowRuns={enrichedFlowRuns}
							onClearFilters={onClearFilters}
						/>
						<FlowRunsPagination
							count={flowRunsCount}
							pages={flowRunsPages}
							pagination={pagination}
							onChangePagination={onPaginationChange}
							onPrefetchPage={onPrefetchPage}
						/>
					</TabsContent>
					<TabsContent value="deployments">
						<DataTable table={deploymentsTable} />
					</TabsContent>
					<TabsContent value="details">
						<DataTable table={metadataTable} />
					</TabsContent>
				</Tabs>
			</div>
			<DeleteFlowDialog
				flow={flow}
				open={showDeleteDialog}
				onOpenChange={setShowDeleteDialog}
			/>
		</>
	);
}
