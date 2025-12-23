import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { type JSX, useCallback, useState } from "react";
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
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { SearchInput } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DeleteFlowDialog } from "./delete-flow-dialog";
import { columns as deploymentColumns } from "./deployment-columns";
import { FlowPageHeader } from "./flow-page-header";
import { FlowStatsSummary } from "./flow-stats-summary";
import {
	getFlowMetadata,
	columns as metadataColumns,
} from "./metadata-columns";

export default function FlowDetail({
	flow,
	flowRuns,
	flowRunsCount,
	flowRunsPages,
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

	return (
		<>
			<div className="container mx-auto">
				<FlowPageHeader
					flow={flow}
					onDelete={() => setShowDeleteDialog(true)}
				/>
				<FlowStatsSummary flowId={flow.id} flow={flow} />
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
						<FlowRunActivityBarGraphTooltipProvider>
							<DataTable table={deploymentsTable} />
						</FlowRunActivityBarGraphTooltipProvider>
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
