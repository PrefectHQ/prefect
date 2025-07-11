import { getRouteApi } from "@tanstack/react-router";
import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useDeferredValue, useMemo } from "react";
import type { GlobalConcurrencyLimit } from "@/api/global-concurrency-limits";
import { DataTable } from "@/components/ui/data-table";
import { SearchInput } from "@/components/ui/input";
import { ActionsCell } from "./actions-cell";
import { ActiveCell } from "./active-cell";

const routeApi = getRouteApi("/concurrency-limits/");

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
			<div className="flex flex-row justify-end">
				<ActionsCell
					{...props}
					onEditRow={onEditRow}
					onDeleteRow={onDeleteRow}
				/>
			</div>
		),
	}),
];

type GlobalConcurrencyLimitsDataTableProps = {
	data: Array<GlobalConcurrencyLimit>;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
};

export const GlobalConcurrencyLimitsDataTable = ({
	data,
	onEditRow,
	onDeleteRow,
}: GlobalConcurrencyLimitsDataTableProps) => {
	const navigate = routeApi.useNavigate();
	const { search } = routeApi.useSearch();
	const deferredSearch = useDeferredValue(search ?? "");

	const filteredData = useMemo(() => {
		return data.filter((row) =>
			row.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	return (
		<Table
			data={filteredData}
			onDeleteRow={onDeleteRow}
			onEditRow={onEditRow}
			searchValue={search}
			onSearchChange={(value) =>
				void navigate({
					to: ".",
					search: (prev) => ({ ...prev, search: value }),
				})
			}
		/>
	);
};

type TableProps = {
	data: Array<GlobalConcurrencyLimit>;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onSearchChange: (value: string) => void;
	searchValue: string | undefined;
};

export function Table({
	data,
	onDeleteRow,
	onEditRow,
	onSearchChange,
	searchValue,
}: TableProps) {
	const table = useReactTable({
		data,
		columns: createColumns({ onDeleteRow, onEditRow }),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(), //load client-side pagination code
	});

	return (
		<div className="flex flex-col gap-4">
			<SearchInput
				className="max-w-72"
				placeholder="Search global concurrency limit"
				value={searchValue}
				onChange={(e) => onSearchChange(e.target.value)}
			/>
			<DataTable table={table} />
		</div>
	);
}
