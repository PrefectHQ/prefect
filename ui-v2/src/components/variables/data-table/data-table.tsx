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
import { useCallback } from "react";
import { SearchInput } from "@/components/ui/input";
import { TagsInput } from "@/components/ui/tags-input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type React from "react";

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
	sorting: components["schemas"]["VariableSort"];
	onSortingChange: (sortKey: components["schemas"]["VariableSort"]) => void;
};

export const VariablesDataTable = ({
	variables,
	currentVariableCount,
	pagination,
	onPaginationChange,
	columnFilters,
	onColumnFiltersChange,
	sorting,
	onSortingChange,
}: VariablesDataTableProps) => {
	const nameSearchValue = columnFilters.find((filter) => filter.id === "name")
		?.value as string;
	const tagsSearchValue = columnFilters.find((filter) => filter.id === "tags")
		?.value as string[];
	const handleNameSearchChange = useCallback(
		(value?: string) => {
			onColumnFiltersChange((prev) => [
				...prev.filter((filter) => filter.id !== "name"),
				{ id: "name", value },
			]);
		},
		[onColumnFiltersChange],
	);

	const handleTagsSearchChange: React.ChangeEventHandler<HTMLInputElement> &
		((tags: string[]) => void) = useCallback(
		(e: string[] | React.ChangeEvent<HTMLInputElement>) => {
			const tags = Array.isArray(e) ? e : e.target.value;

			onColumnFiltersChange((prev) => [
				...prev.filter((filter) => filter.id !== "tags"),
				{ id: "tags", value: tags },
			]);
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
		<div>
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					<p className="text-sm text-muted-foreground">
						{currentVariableCount} Variables
					</p>
				</div>
				<div className="sm:col-span-2 md:col-span-2 lg:col-span-3">
					<SearchInput
						placeholder="Search variables"
						value={nameSearchValue}
						onChange={(e) => handleNameSearchChange(e.target.value)}
					/>
				</div>
				<div className="xs:col-span-1 md:col-span-2 lg:col-span-3">
					<TagsInput
						placeholder="Filter by tags"
						onChange={handleTagsSearchChange}
						value={tagsSearchValue}
					/>
				</div>
				<div className="xs:col-span-1 md:col-span-2 lg:col-span-2">
					<Select value={sorting} onValueChange={onSortingChange}>
						<SelectTrigger aria-label="Variable sort order">
							<SelectValue placeholder="Sort by" />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value="CREATED_DESC">Created</SelectItem>
							<SelectItem value="UPDATED_DESC">Updated</SelectItem>
							<SelectItem value="NAME_ASC">A to Z</SelectItem>
							<SelectItem value="NAME_DESC">Z to A</SelectItem>
						</SelectContent>
					</Select>
				</div>
			</div>
			<DataTable table={table} />
		</div>
	);
};
