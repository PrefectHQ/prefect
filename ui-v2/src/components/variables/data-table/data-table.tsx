import type { components } from "@/api/prefect";
import {
	useReactTable,
	getCoreRowModel,
	createColumnHelper,
	type PaginationState,
	type OnChangeFn,
	type ColumnFiltersState,
} from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { ActionsCell } from "./cells";
import { useCallback, useRef } from "react";
import { VariablesDataTableSearch } from "./search";

const columnHelper = createColumnHelper<components["schemas"]["Variable"]>();

const columns = [
	columnHelper.accessor("name", {
		header: "Name",
	}),
	columnHelper.accessor("value", {
		header: "Value",
		cell: (props) => {
			const value = props.getValue();
			if (!value) return null;
			return (
				<code className="rounded bg-muted px-2 py-1 font-mono text-sm">
					{JSON.stringify(value)}
				</code>
			);
		},
	}),
	columnHelper.accessor("updated", {
		header: "Updated",
		cell: (props) => {
			const updated = props.getValue();
			if (!updated) return null;
			return new Date(updated ?? new Date())
				.toLocaleString(undefined, {
					year: "numeric",
					month: "numeric",
					day: "numeric",
					hour: "numeric",
					minute: "numeric",
					second: "numeric",
					hour12: true,
				})
				.replace(",", "");
		},
	}),
	columnHelper.accessor("tags", {
		header: () => null,
		cell: (props) => {
			const tags = props.getValue();
			if (!tags) return null;
			return (
				<div className="flex flex-row gap-1 justify-end">
					{tags?.map((tag) => (
						<Badge key={tag}>{tag}</Badge>
					))}
				</div>
			);
		},
	}),
	columnHelper.display({
		id: "actions",
		cell: ActionsCell,
	}),
];

type VariablesDataTableProps = {
	variables: components["schemas"]["Variable"][];
	currentVariableCount: number;
	pagination: PaginationState;
	onPaginationChange: OnChangeFn<PaginationState>;
	columnFilters: ColumnFiltersState;
	onColumnFiltersChange: OnChangeFn<ColumnFiltersState>;
};

export const VariablesDataTable = ({
	variables,
	currentVariableCount,
	pagination,
	onPaginationChange,
	columnFilters,
	onColumnFiltersChange,
}: VariablesDataTableProps) => {
	const initialSearchValue = useRef(
		columnFilters.find((filter) => filter.id === "name")?.value as string,
	);
	const handleNameSearchChange = useCallback(
		(value: string) => {
			onColumnFiltersChange([{ id: "name", value }]);
		},
		[onColumnFiltersChange],
	);

	const handleSortChange = useCallback(
		(value: string) => {
			onColumnFiltersChange([{ id: "sort", value }]);
		},
		[onColumnFiltersChange],
	);

	const table = useReactTable({
		data: variables,
		columns: columns,
		state: {
			pagination,
			columnFilters,
		},
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		onPaginationChange: onPaginationChange,
		onColumnFiltersChange: onColumnFiltersChange,
		rowCount: currentVariableCount,
	});

	return (
		<div className="flex flex-col gap-6 mt-2">
			<div className="flex items-center justify-between">
				<p className="text-sm text-muted-foreground">
					{currentVariableCount} Variables
				</p>
				<VariablesDataTableSearch
					initialSearchValue={initialSearchValue.current}
					onNameSearchChange={handleNameSearchChange}
					onSortChange={handleSortChange}
				/>
			</div>
			<DataTable table={table} />
		</div>
	);
};
