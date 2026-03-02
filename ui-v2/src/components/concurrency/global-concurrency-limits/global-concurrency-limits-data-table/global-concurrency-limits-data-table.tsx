import { getRouteApi } from "@tanstack/react-router";
import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useDeferredValue, useMemo } from "react";
import type { GlobalConcurrencyLimit } from "@/api/global-concurrency-limits";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
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

	const onClearSearch = () => {
		void navigate({
			to: ".",
			search: (prev) => ({ ...prev, search: "" }),
		});
	};

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
			showFilteredEmptyState={data.length > 0 && filteredData.length === 0}
			onClearSearch={onClearSearch}
		/>
	);
};

const GlobalConcurrencyLimitsFilteredEmptyState = ({
	onClearSearch,
}: {
	onClearSearch: () => void;
}) => (
	<EmptyState>
		<EmptyStateIcon id="Search" />
		<EmptyStateTitle>
			No global concurrency limits match your search
		</EmptyStateTitle>
		<EmptyStateDescription>
			Try adjusting your search terms.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button variant="outline" onClick={onClearSearch}>
				Clear search
			</Button>
		</EmptyStateActions>
	</EmptyState>
);

type TableProps = {
	data: Array<GlobalConcurrencyLimit>;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onSearchChange: (value: string) => void;
	searchValue: string | undefined;
	showFilteredEmptyState: boolean;
	onClearSearch: () => void;
};

export function Table({
	data,
	onDeleteRow,
	onEditRow,
	onSearchChange,
	searchValue,
	showFilteredEmptyState,
	onClearSearch,
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
			{showFilteredEmptyState ? (
				<GlobalConcurrencyLimitsFilteredEmptyState
					onClearSearch={onClearSearch}
				/>
			) : (
				<DataTable table={table} />
			)}
		</div>
	);
}
