import { useSuspenseQuery } from "@tanstack/react-query";
import {
	getCoreRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { buildListWorkPoolWorkersQuery } from "@/api/work-pools";
import { createWorkersTableColumnsWithActions } from "../components/workers-table-columns";
import { WorkersTableRowActions } from "../components/workers-table-row-actions";

export const useWorkersTable = (workPoolName: string) => {
	const [searchQuery, setSearchQuery] = useState("");

	const {
		data: workers = [],
		isLoading,
		error,
	} = useSuspenseQuery(buildListWorkPoolWorkersQuery(workPoolName));

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
		initialState: {
			sorting: [{ id: "name", desc: false }],
		},
	});

	return {
		table,
		searchQuery,
		setSearchQuery,
		workers,
		filteredWorkers,
		isLoading,
		error,
	};
};
