import { DataTable } from "@/components/ui/data-table";
import { cn } from "@/lib/utils";
import { WorkersTableEmptyState } from "./components/workers-table-empty-state";
import { WorkersTableToolbar } from "./components/workers-table-toolbar";
import { useWorkersTable } from "./hooks/use-workers-table";
import type { WorkersTableProps } from "./types";

export const WorkersTable = ({
	workPoolName,
	className,
}: WorkersTableProps) => {
	const { table, searchQuery, setSearchQuery, workers, filteredWorkers } =
		useWorkersTable(workPoolName);

	// Show empty state when no workers at all or no search results
	const showEmptyState =
		workers.length === 0 || (searchQuery && filteredWorkers.length === 0);

	if (showEmptyState) {
		return (
			<div className={cn("space-y-4", className)}>
				<WorkersTableToolbar
					searchQuery={searchQuery}
					onSearchChange={setSearchQuery}
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
				onSearchChange={setSearchQuery}
				resultsCount={filteredWorkers.length}
				totalCount={workers.length}
			/>
			<DataTable table={table} />
		</div>
	);
};
