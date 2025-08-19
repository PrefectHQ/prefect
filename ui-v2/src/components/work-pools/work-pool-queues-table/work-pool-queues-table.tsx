import type {
	OnChangeFn,
	RowSelectionState,
	SortingState,
} from "@tanstack/react-table";
import {
	getCoreRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useCallback, useState } from "react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { DataTable } from "@/components/ui/data-table";
import { cn } from "@/lib/utils";
import { enhancedWorkPoolQueuesTableColumns } from "./components/enhanced-work-pool-queues-table-columns";
import { WorkPoolQueuesTableEmptyState } from "./components/work-pool-queues-table-empty-state";
import { WorkPoolQueuesTableToolbar } from "./components/work-pool-queues-table-toolbar";

type WorkPoolQueuesTableProps = {
	queues: WorkPoolQueue[];
	searchQuery: string;
	sortState: SortingState;
	totalCount: number;
	workPoolName: string;
	enableBulkOperations?: boolean; // New optional prop
	className?: string;
	onSearchChange: (query: string) => void;
	onSortingChange: OnChangeFn<SortingState>;
};

export const WorkPoolQueuesTable = ({
	queues,
	searchQuery,
	sortState,
	totalCount,
	workPoolName,
	enableBulkOperations = true,
	className,
	onSearchChange,
	onSortingChange,
}: WorkPoolQueuesTableProps) => {
	// Leverage Tanstack Table's row selection state
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	const handleSortingChange: OnChangeFn<SortingState> = useCallback(
		(updater) => {
			let newSorting = sortState;
			if (typeof updater === "function") {
				newSorting = updater(sortState);
			} else {
				newSorting = updater;
			}
			onSortingChange(newSorting);
		},
		[sortState, onSortingChange],
	);

	// Enhanced table configuration with selection support
	const table = useReactTable({
		data: queues,
		columns: enhancedWorkPoolQueuesTableColumns,
		// Core features
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		// Selection features from @tanstack/react-table
		onRowSelectionChange: setRowSelection,
		state: {
			rowSelection,
			sorting: sortState,
		},
		// Control which rows can be selected
		enableRowSelection: (row) => {
			// Disable selection for default queue
			return row.original.name !== "default";
		},
		onSortingChange: handleSortingChange,
		initialState: {
			sorting: [{ id: "name", desc: false }],
		},
	});

	const resultsCount = queues.length;

	return (
		<div className={cn("space-y-4", className)}>
			<WorkPoolQueuesTableToolbar
				searchQuery={searchQuery}
				onSearchChange={onSearchChange}
				resultsCount={resultsCount}
				totalCount={totalCount}
				workPoolName={workPoolName}
				// Pass table instance for bulk operations
				table={enableBulkOperations ? table : undefined}
			/>
			{resultsCount === 0 ? (
				<WorkPoolQueuesTableEmptyState
					hasSearchQuery={!!searchQuery}
					workPoolName={workPoolName}
				/>
			) : (
				<DataTable table={table} />
			)}
		</div>
	);
};
