import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import type { ChangeEvent } from "react";
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
	useFlowRunsSelectedRows,
} from "@/components/flow-runs/flow-runs-list";
import { SortFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/sort-filter";
import { StateFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import { DataTable } from "@/components/ui/data-table";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { SearchInput } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TagsInput } from "@/components/ui/tags-input";
import { DeleteFlowDialog } from "./delete-flow-dialog";
import { columns as deploymentColumns } from "./deployment-columns";
import { FlowDetails } from "./flow-details";
import { FlowPageHeader } from "./flow-page-header";
import { FlowStatsSummary } from "./flow-stats-summary";

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
	deploymentSearch,
	onDeploymentSearchChange,
	deploymentTags,
	onDeploymentTagsChange,
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
	deploymentSearch: string | undefined;
	onDeploymentSearchChange: (search: string) => void;
	deploymentTags: string[];
	onDeploymentTagsChange: (tags: string[]) => void;
}): JSX.Element {
	const navigate = useNavigate();
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [selectedRows, setSelectedRows, { onSelectRow, clearSet }] =
		useFlowRunsSelectedRows();

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

	// Enrich paginated flow runs with flow object for the list
	const enrichedFlowRuns: FlowRunCardData[] = flowRuns.map((flowRun) => ({
		...flowRun,
		flow: flow,
	}));

	// Handler to clear filters
	const onClearFilters = useCallback(() => {
		onFlowRunSearchChange("");
		onSelectFilter(new Set());
		clearSet();
	}, [onFlowRunSearchChange, onSelectFilter, clearSet]);

	// Handler for deployment tags that satisfies both ChangeEventHandler and (tags: string[]) => void
	// This is needed because TagsInput's onChange prop type is an intersection of both signatures
	const handleDeploymentTagsChange: React.ChangeEventHandler<HTMLInputElement> &
		((tags: string[]) => void) = useCallback(
		(e: string[] | ChangeEvent<HTMLInputElement>) => {
			if (Array.isArray(e)) {
				onDeploymentTagsChange(e);
			}
		},
		[onDeploymentTagsChange],
	);

	return (
		<>
			<div className="container mx-auto flex flex-col gap-4">
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
						<div className="flex items-center justify-between">
							<FlowRunsRowCount
								count={flowRunsCount}
								results={enrichedFlowRuns}
								selectedRows={selectedRows}
								setSelectedRows={setSelectedRows}
							/>
							<div className="flex items-center gap-4">
								<SearchInput
									placeholder="Search by run name"
									value={flowRunSearch ?? ""}
									onChange={(e) => onFlowRunSearchChange(e.target.value)}
									className="w-64"
								/>
								<StateFilter
									selectedFilters={selectedStates}
									onSelectFilter={onSelectFilter}
								/>
								<SortFilter value={sort} onSelect={onSortChange} />
							</div>
						</div>
						<FlowRunsList
							flowRuns={enrichedFlowRuns}
							selectedRows={selectedRows}
							onSelect={onSelectRow}
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
						<header className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
							<SearchInput
								placeholder="Search deployments..."
								value={deploymentSearch ?? ""}
								onChange={(e) => onDeploymentSearchChange(e.target.value)}
							/>
							<TagsInput
								placeholder="Filter by tags"
								value={deploymentTags}
								onChange={handleDeploymentTagsChange}
							/>
						</header>
						<FlowRunActivityBarGraphTooltipProvider>
							{/* Override table container overflow to allow chart tooltips to escape */}
							<div className="[&_[data-slot=table-container]]:overflow-visible">
								<DataTable table={deploymentsTable} />
							</div>
						</FlowRunActivityBarGraphTooltipProvider>
					</TabsContent>
					<TabsContent value="details">
						<FlowDetails flow={flow} />
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
