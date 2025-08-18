import { useSuspenseQuery } from "@tanstack/react-query";
import {
	getCoreRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import { DataTable } from "@/components/ui/data-table";
import { cn } from "@/lib/utils";
import { workPoolQueuesTableColumns } from "./components/work-pool-queues-table-columns";
import { WorkPoolQueuesTableEmptyState } from "./components/work-pool-queues-table-empty-state";
import { WorkPoolQueuesTableToolbar } from "./components/work-pool-queues-table-toolbar";

interface WorkPoolQueuesTableProps {
	workPoolName: string;
	className?: string;
}

export const WorkPoolQueuesTable = ({
	workPoolName,
	className,
}: WorkPoolQueuesTableProps) => {
	const { data: queues = [] } = useSuspenseQuery(
		buildListWorkPoolQueuesQuery(workPoolName),
	);

	const [searchQuery, setSearchQuery] = useState("");

	const filteredQueues = useMemo(() => {
		if (!searchQuery) return queues;
		return queues.filter((queue) =>
			queue.name.toLowerCase().includes(searchQuery.toLowerCase()),
		);
	}, [queues, searchQuery]);

	const table = useReactTable({
		data: filteredQueues,
		columns: workPoolQueuesTableColumns,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		initialState: {
			sorting: [{ id: "name", desc: false }],
		},
	});

	return (
		<div className={cn("space-y-4", className)}>
			<WorkPoolQueuesTableToolbar
				searchQuery={searchQuery}
				onSearchChange={setSearchQuery}
				resultsCount={filteredQueues.length}
				totalCount={queues.length}
				workPoolName={workPoolName}
			/>
			{filteredQueues.length === 0 ? (
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
