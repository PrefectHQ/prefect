import { DataTable } from "@/components/ui/data-table";
import { type GlobalConcurrencyLimit } from "@/hooks/global-concurrency-limits";
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
import { ActiveCell } from "./active-cell";

const routeApi = getRouteApi("/concurrency-limits");

const columnHelper = createColumnHelper<GlobalConcurrencyLimit>();

const createColumns = ({
	onEditRow,
	onDeleteRow,
}: {
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
}) => [
	columnHelper.accessor("name", {
		header: "Name",
	}),
	columnHelper.accessor("limit", {
		header: "Limit",
	}),
	columnHelper.accessor("active_slots", {
		header: "Active Slots",
	}),
	columnHelper.accessor("slot_decay_per_second", {
		header: "Slots Decay Per Second",
	}),
	columnHelper.accessor("active", {
		header: "Active",
		cell: ActiveCell,
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => (
			<ActionsCell {...props} onEditRow={onEditRow} onDeleteRow={onDeleteRow} />
		),
	}),
];

type Props = {
	data: Array<GlobalConcurrencyLimit>;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
};

export const GlobalConcurrencyDataTable = ({
	data,
	onEditRow,
	onDeleteRow,
}: Props) => {
	const navigate = routeApi.useNavigate();
	const { search } = routeApi.useSearch();
	const deferredSearch = useDeferredValue(search ?? "");

	const filteredData = useMemo(() => {
		return data.filter((row) =>
			row.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const table = useReactTable({
		data: filteredData,
		columns: createColumns({ onEditRow, onDeleteRow }),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(), //load client-side pagination code
	});

	return (
		<div className="flex flex-col gap-4">
			<SearchInput
				placeholder="Search global concurrency limit"
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
