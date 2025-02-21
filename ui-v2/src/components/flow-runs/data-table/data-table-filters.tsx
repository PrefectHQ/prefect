import type { Deployment } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import { Flow } from "@/api/flows";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";

import { use } from "react";

import { RunNameSearch } from "./flow-runs-filters/run-name-search";
import { SortFilter } from "./flow-runs-filters/sort-filter";
import type { SortFilters } from "./flow-runs-filters/sort-filter.constants";
import { StateFilter } from "./flow-runs-filters/state-filter";
import type { FlowRunState } from "./flow-runs-filters/state-filters.constants";
import { RowSelectionContext } from "./row-selection-context";
import { useDeleteFlowRunsDialog } from "./use-delete-flow-runs-dialog";

export type FlowRunsDataTableRow = FlowRun & {
	flow: Flow;
	numTaskRuns?: number;
	deployment?: Deployment;
};

export type FlowRunsFiltersProps = {
	search: {
		onChange: (value: string) => void;
		value: string;
	};
	stateFilter: {
		value: Set<FlowRunState>;
		onSelect: (filters: Set<FlowRunState>) => void;
	};
	sort: {
		value: SortFilters | undefined;
		onSelect: (sort: SortFilters) => void;
	};
	flowRunsCount: number | undefined;
};

export const FlowRunsFilters = ({
	search,
	sort,
	stateFilter,
	flowRunsCount,
}: FlowRunsFiltersProps) => {
	const rowSelectionCtx = use(RowSelectionContext);
	if (!rowSelectionCtx) {
		throw new Error(
			"'FlowRunsFilters' must be a child of `RowSelectionContext`",
		);
	}
	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteFlowRunsDialog();

	const renderFlowRunCount = (selectedRows: Array<string>) => {
		if (selectedRows.length > 0) {
			return (
				<div className="flex items-center gap-1">
					<Typography variant="bodySmall" className="text-muted-foreground">
						{selectedRows.length} selected
					</Typography>
					<Button
						aria-label="Delete rows"
						size="icon"
						variant="secondary"
						onClick={() => {
							confirmDelete(selectedRows, () =>
								rowSelectionCtx.setRowSelection({}),
							);
						}}
					>
						<Icon id="Trash2" className="h-4 w-4" />
					</Button>
				</div>
			);
		}
		if (flowRunsCount) {
			return (
				<Typography variant="bodySmall" className="text-muted-foreground">
					{flowRunsCount} {pluralize(flowRunsCount, "Flow run")}
				</Typography>
			);
		}
		return null;
	};

	return (
		<>
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					{renderFlowRunCount(Object.keys(rowSelectionCtx.rowSelection))}
				</div>
				<div className="sm:col-span-2 md:col-span-2 lg:col-span-3">
					<RunNameSearch
						value={search.value}
						onChange={(e) => search.onChange(e.target.value)}
						placeholder="Search by run name"
					/>
				</div>
				<div className="xs:col-span-1 md:col-span-2 lg:col-span-3">
					<StateFilter
						selectedFilters={stateFilter.value}
						onSelectFilter={stateFilter.onSelect}
					/>
				</div>

				<div className="xs:col-span-1 md:col-span-2 lg:col-span-2">
					<SortFilter value={sort.value} onSelect={sort.onSelect} />
				</div>
			</div>
			<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
		</>
	);
};
