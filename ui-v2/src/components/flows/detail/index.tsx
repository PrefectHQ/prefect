import { useNavigate } from "@tanstack/react-router";
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
import { SearchInput } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DeleteFlowDialog } from "./delete-flow-dialog";
import { FlowDeploymentsTab } from "./flow-deployments-tab";
import { FlowDetails } from "./flow-details";
import { FlowPageHeader } from "./flow-page-header";
import { FlowStatsSummary } from "./flow-stats-summary";

export default function FlowDetail({
	flow,
	flowRuns,
	flowRunsCount,
	flowRunsPages,
	deployments,
	deploymentsCount,
	deploymentsPages,
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
	deploymentSort,
	onDeploymentSortChange,
	deploymentPagination,
	onDeploymentPaginationChange,
}: {
	flow: Flow;
	flowRuns: FlowRun[];
	flowRunsCount: number;
	flowRunsPages: number;
	deployments: components["schemas"]["DeploymentResponse"][];
	deploymentsCount: number;
	deploymentsPages: number;
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
	deploymentSort: components["schemas"]["DeploymentSort"];
	onDeploymentSortChange: (
		sort: components["schemas"]["DeploymentSort"],
	) => void;
	deploymentPagination: { page: number; limit: number };
	onDeploymentPaginationChange: (pagination: {
		page: number;
		limit: number;
	}) => void;
}): JSX.Element {
	const navigate = useNavigate();
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [selectedRows, setSelectedRows, { onSelectRow, clearSet }] =
		useFlowRunsSelectedRows();

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
					<TabsContent value="runs" className="flex flex-col gap-4">
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
						<FlowDeploymentsTab
							deployments={deployments}
							deploymentsCount={deploymentsCount}
							deploymentsPages={deploymentsPages}
							deploymentSearch={deploymentSearch}
							onDeploymentSearchChange={onDeploymentSearchChange}
							deploymentTags={deploymentTags}
							onDeploymentTagsChange={onDeploymentTagsChange}
							deploymentSort={deploymentSort}
							onDeploymentSortChange={onDeploymentSortChange}
							deploymentPagination={deploymentPagination}
							onDeploymentPaginationChange={onDeploymentPaginationChange}
						/>
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
