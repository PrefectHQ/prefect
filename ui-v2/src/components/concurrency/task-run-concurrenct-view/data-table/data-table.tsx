import { DataTable } from "@/components/ui/data-table";
import { type TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { getRouteApi } from "@tanstack/react-router";
import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";

import { SearchInput } from "@/components/ui/input";
import { useDeferredValue, useMemo } from "react";
import { ActionsCell } from "./actions-cell";

const routeApi = getRouteApi("/concurrency-limits");

const columnHelper = createColumnHelper<TaskRunConcurrencyLimit>();

const createColumns = ({
	onDeleteRow,
	onResetRow,
}: {
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
}) => [
	columnHelper.accessor("tag", {
		header: "Tag", // TODO: Make this a link when starting the tak run concurrency page
	}),
	columnHelper.accessor("concurrency_limit", {
		header: "Slots",
	}),
	columnHelper.accessor("active_slots", {
		header: "Active Task Runs", // TODO: Give this styling once knowing what it looks like
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => (
			<ActionsCell
				{...props}
				onDeleteRow={onDeleteRow}
				onResetRow={onResetRow}
			/>
		),
	}),
];

type Props = {
	data: Array<TaskRunConcurrencyLimit>;
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
};

export const TaskRunConcurrencyDataTable = ({
	data,
	onDeleteRow,
	onResetRow,
}: Props) => {
	const navigate = routeApi.useNavigate();
	const { search } = routeApi.useSearch();
	const deferredSearch = useDeferredValue(search ?? "");

	const filteredData = useMemo(() => {
		return data.filter((row) =>
			row.tag.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const table = useReactTable({
		data: filteredData,
		columns: createColumns({ onDeleteRow, onResetRow }),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(), //load client-side pagination code
	});

	return (
		<div className="flex flex-col gap-4">
			<SearchInput
				placeholder="Search active task limit"
				value={search}
				onChange={(e) =>
					void navigate({
						to: ".",
						search: (prev) => ({ ...prev, search: e.target.value }),
					})
				}
			/>
			<DataTable table={table} />
		</div>
	);
};
