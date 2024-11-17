import { DataTable } from "@/components/ui/data-table";
import { components } from "@/api/prefect";
import {
	useReactTable,
	getCoreRowModel,
	createColumnHelper,
	type PaginationState,
	type OnChangeFn,
	type ColumnFiltersState,
} from "@tanstack/react-table";
import { useCallback } from "react";
import { Search } from "./search";
import {
	StatusCell,
	ConcurrencyCell,
	LastHeartbeatCell,
	ActionsCell,
} from "./cells";
import { Checkbox } from "@/components/ui/checkbox";

const columnHelper = createColumnHelper<components["schemas"]["WorkPool"]>();

const columns = [
	columnHelper.display({
		id: "select",
		header: ({ table }) => (
			<Checkbox
				checked={table.getIsAllPageRowsSelected()}
				onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
				aria-label="Select all"
			/>
		),
		cell: ({ row }) => (
			<Checkbox
				checked={row.getIsSelected()}
				onCheckedChange={(value) => row.toggleSelected(!!value)}
				aria-label="Select row"
			/>
		),
		enableSorting: false,
		enableHiding: false,
	}),
	columnHelper.accessor("name", {
		header: "Name",
	}),
	columnHelper.accessor("type", {
		header: "Type",
	}),
	columnHelper.accessor("is_paused", {
		header: "Status",
		cell: StatusCell,
	}),
	columnHelper.accessor("concurrency_limit", {
		header: "Concurrency",
		cell: ConcurrencyCell,
	}),
	columnHelper.display({
		id: "lastHeartbeat",
		cell: ({ row }) => <LastHeartbeatCell row={row} />,
	}),
	columnHelper.display({
		id: "actions",
		cell: ActionsCell,
	}),
];

type WorkPoolsDataTableProps = {
	workPools: components["schemas"]["WorkPool"][];
	filteredWorkPoolsCount: number;
	pagination: PaginationState;
	onPaginationChange: OnChangeFn<PaginationState>;
	columnFilters?: ColumnFiltersState;
	onColumnFiltersChange?: OnChangeFn<ColumnFiltersState>;
};

export const WorkPoolsDataTable = ({
	workPools,
	filteredWorkPoolsCount,
	pagination,
	onPaginationChange,
	columnFilters = [],
	onColumnFiltersChange,
}: WorkPoolsDataTableProps) => {
	const nameSearchValue = columnFilters.find((filter) => filter.id === "name")
		?.value as string;

	const handleNameSearchChange = useCallback(
		(value?: string) => {
			onColumnFiltersChange?.((prev) => [
				...prev.filter((filter) => filter.id !== "name"),
				{ id: "name", value },
			]);
		},
		[onColumnFiltersChange],
	);

	const table = useReactTable({
		data: workPools,
		columns: columns,
		state: {
			pagination,
			columnFilters,
		},
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		onPaginationChange,
		onColumnFiltersChange,
		rowCount: filteredWorkPoolsCount,
		enableRowSelection: true,
	});

	return (
		<div>
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					<p className="text-sm text-muted-foreground">
						{filteredWorkPoolsCount} Work Pools
					</p>
				</div>
				<Search
					nameSearchValue={nameSearchValue}
					onNameSearchChange={handleNameSearchChange}
				/>
			</div>
			<DataTable table={table} />
		</div>
	);
};
