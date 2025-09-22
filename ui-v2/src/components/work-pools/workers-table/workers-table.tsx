import type {
	ColumnFiltersState,
	OnChangeFn,
	PaginationState,
} from "@tanstack/react-table";
import {
	getCoreRowModel,
	getPaginationRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useCallback, useMemo } from "react";
import type { WorkPoolWorker } from "@/api/work-pools";
import { DataTable } from "@/components/ui/data-table";
import { cn } from "@/utils";
import { createWorkersTableColumnsWithActions } from "./components/workers-table-columns";
import { WorkersTableEmptyState } from "./components/workers-table-empty-state";
import { WorkersTableRowActions } from "./components/workers-table-row-actions";
import { WorkersTableToolbar } from "./components/workers-table-toolbar";

export type WorkersTableProps = {
	workPoolName: string;
	workers: WorkPoolWorker[];
	pagination: PaginationState;
	columnFilters: ColumnFiltersState;
	onPaginationChange: (pagination: PaginationState) => void;
	onColumnFiltersChange: (columnFilters: ColumnFiltersState) => void;
	className?: string;
};

export const WorkersTable = ({
	workPoolName,
	workers,
	pagination,
	columnFilters,
	onPaginationChange,
	onColumnFiltersChange,
	className,
}: WorkersTableProps) => {
	const searchQuery = (columnFilters.find((filter) => filter.id === "name")
		?.value ?? "") as string;

	const handleSearchChange = useCallback(
		(value: string) => {
			const filters = columnFilters.filter((filter) => filter.id !== "name");
			onColumnFiltersChange(
				value ? [...filters, { id: "name", value }] : filters,
			);
		},
		[onColumnFiltersChange, columnFilters],
	);

	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			onPaginationChange(newPagination);
		},
		[pagination, onPaginationChange],
	);

	const filteredWorkers = useMemo(() => {
		if (!searchQuery) return workers;
		return workers.filter((worker) =>
			worker.name.toLowerCase().includes(searchQuery.toLowerCase()),
		);
	}, [workers, searchQuery]);

	const columns = useMemo(
		() =>
			createWorkersTableColumnsWithActions({
				workPoolName,
				ActionsComponent: WorkersTableRowActions,
			}),
		[workPoolName],
	);

	const table = useReactTable({
		data: filteredWorkers,
		columns,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		manualPagination: false,
		state: {
			pagination,
		},
		onPaginationChange: handlePaginationChange,
		initialState: {
			sorting: [{ id: "name", desc: false }],
		},
	});

	// Show empty state when no workers at all or no search results
	const showEmptyState =
		workers.length === 0 || (searchQuery && filteredWorkers.length === 0);

	if (showEmptyState) {
		return (
			<div className={cn("space-y-4", className)}>
				<WorkersTableToolbar
					searchQuery={searchQuery}
					onSearchChange={handleSearchChange}
					resultsCount={filteredWorkers.length}
					totalCount={workers.length}
				/>
				<WorkersTableEmptyState
					hasSearchQuery={searchQuery.length > 0}
					workPoolName={workPoolName}
				/>
			</div>
		);
	}

	return (
		<div className={cn("space-y-4", className)}>
			<WorkersTableToolbar
				searchQuery={searchQuery}
				onSearchChange={handleSearchChange}
				resultsCount={filteredWorkers.length}
				totalCount={workers.length}
			/>
			<DataTable table={table} />
		</div>
	);
};
