import type { OnChangeFn, SortingState } from "@tanstack/react-table";
import {
	getCoreRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useCallback } from "react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { DataTable } from "@/components/ui/data-table";
import { cn } from "@/utils";
import { createWorkPoolQueuesTableColumns } from "./components/work-pool-queues-table-columns";
import { WorkPoolQueuesTableEmptyState } from "./components/work-pool-queues-table-empty-state";
import { WorkPoolQueuesTableToolbar } from "./components/work-pool-queues-table-toolbar";

type WorkPoolQueuesTableProps = {
	queues: WorkPoolQueue[];
	searchQuery: string;
	sortState: SortingState;
	totalCount: number;
	workPoolName: string;
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
	className,
	onSearchChange,
	onSortingChange,
}: WorkPoolQueuesTableProps) => {
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

	// Create columns with late indicator enabled
	const columns = createWorkPoolQueuesTableColumns({
		enableLateIndicator: true,
	});

	// Enhanced table configuration
	const table = useReactTable({
		data: queues,
		columns,
		// Core features
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		state: {
			sorting: sortState,
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
