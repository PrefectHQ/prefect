import type { Table } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { BulkOperationsToolbar } from "./bulk-operations-toolbar";

type WorkPoolQueuesTableToolbarProps = {
	searchQuery: string;
	onSearchChange: (query: string) => void;
	resultsCount: number;
	totalCount: number;
	workPoolName: string;
	// Optional table instance for bulk operations
	table?: Table<WorkPoolQueue>;
	className?: string;
};

export const WorkPoolQueuesTableToolbar = ({
	searchQuery,
	onSearchChange,
	resultsCount,
	totalCount,
	workPoolName,
	table,
	className,
}: WorkPoolQueuesTableToolbarProps) => {
	const showClearFilters = searchQuery.length > 0;

	// Use Tanstack Table's selection state if table is provided
	const selectedRows = table?.getFilteredSelectedRowModel().rows ?? [];
	const hasSelection = selectedRows.length > 0;
	const selectedQueues = selectedRows.map((row) => row.original);

	return (
		<div className={cn("space-y-4", className)}>
			{/* Main toolbar */}
			<div className="flex items-center justify-between">
				<div className="flex items-center space-x-2">
					<div className="text-sm text-muted-foreground">
						{searchQuery
							? `${resultsCount} of ${totalCount} Work Queue${totalCount !== 1 ? "s" : ""}`
							: `${totalCount} Work Queue${totalCount !== 1 ? "s" : ""}`}
					</div>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => {
							// TODO: Implement filter/actions menu
							console.log("Filter/actions for work queues");
						}}
					>
						<Plus className="h-4 w-4" />
					</Button>
				</div>

				<div className="flex items-center space-x-2">
					{showClearFilters && (
						<Button
							variant="ghost"
							size="sm"
							onClick={() => onSearchChange("")}
						>
							Clear filters
						</Button>
					)}
					<div className="relative">
						<Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
						<Input
							placeholder="Search"
							value={searchQuery}
							onChange={(e) => onSearchChange(e.target.value)}
							className="pl-8 w-64"
						/>
					</div>
				</div>
			</div>

			{/* Bulk operations toolbar - only show if table instance is provided */}
			{table && hasSelection && (
				<BulkOperationsToolbar
					selectedQueues={selectedQueues}
					onClearSelection={() => table.toggleAllRowsSelected(false)}
					workPoolName={workPoolName}
				/>
			)}
		</div>
	);
};
