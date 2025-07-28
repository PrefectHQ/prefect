import {
	type ColumnFiltersState,
	createColumnHelper,
	getCoreRowModel,
	type OnChangeFn,
	type PaginationState,
	useReactTable,
} from "@tanstack/react-table";
import type React from "react";
import { useCallback, useMemo } from "react";
import type { components } from "@/api/prefect";
import { DataTable } from "@/components/ui/data-table";
import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { TagsInput } from "@/components/ui/tags-input";
import { pluralize } from "@/utils";
import { ActionsCell, ValueCell } from "./cells";

const columnHelper = createColumnHelper<components["schemas"]["Variable"]>();

const createColumns = (
	onVariableEdit: (variable: components["schemas"]["Variable"]) => void,
) => [
	columnHelper.accessor("name", {
		header: "Name",
	}),
	columnHelper.accessor("value", {
		header: "Value",
		cell: ValueCell,
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
			return <TagBadgeGroup tags={tags} maxTagsDisplayed={3} />;
		},
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => <ActionsCell {...props} onVariableEdit={onVariableEdit} />,
	}),
];

type VariablesDataTableProps = {
	variables: components["schemas"]["Variable"][];
	currentVariableCount: number;
	pagination: PaginationState;
	onPaginationChange: (newPagination: PaginationState) => void;
	columnFilters: ColumnFiltersState;
	onColumnFiltersChange: (newColumnFilters: ColumnFiltersState) => void;
	sorting: components["schemas"]["VariableSort"];
	onSortingChange: (sortKey: components["schemas"]["VariableSort"]) => void;
	onVariableEdit: (variable: components["schemas"]["Variable"]) => void;
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
	onVariableEdit,
}: VariablesDataTableProps) => {
	const columns = useMemo(
		() => createColumns(onVariableEdit),
		[onVariableEdit],
	);

	const nameSearchValue = columnFilters.find((filter) => filter.id === "name")
		?.value as string;
	const tagsSearchValue = columnFilters.find((filter) => filter.id === "tags")
		?.value as string[];
	const handleNameSearchChange = useCallback(
		(value?: string) => {
			const filters = columnFilters.filter((filter) => filter.id !== "name");
			onColumnFiltersChange(
				value ? [...filters, { id: "name", value }] : filters,
			);
		},
		[onColumnFiltersChange, columnFilters],
	);

	const handleTagsSearchChange: React.ChangeEventHandler<HTMLInputElement> &
		((tags: string[]) => void) = useCallback(
		(e: string[] | React.ChangeEvent<HTMLInputElement>) => {
			const tags = Array.isArray(e) ? e : e.target.value;
			const filters = columnFilters.filter((filter) => filter.id !== "tags");
			onColumnFiltersChange(
				tags.length ? [...filters, { id: "tags", value: tags }] : filters,
			);
		},
		[onColumnFiltersChange, columnFilters],
	);

	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			onPaginationChange(newPagination);
		},
		[pagination, onPaginationChange],
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
		onPaginationChange: handlePaginationChange,
		rowCount: currentVariableCount,
		defaultColumn: {
			maxSize: 300,
		},
	});

	return (
		<div>
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					<p className="text-sm text-muted-foreground">
						{currentVariableCount} {pluralize(currentVariableCount, "Variable")}
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
						<SelectTrigger aria-label="Variable sort order" className="w-full">
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
