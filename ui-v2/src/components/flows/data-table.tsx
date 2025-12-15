import type {
	ColumnFiltersState,
	OnChangeFn,
	PaginationState,
} from "@tanstack/react-table";
import {
	getCoreRowModel,
	type RowSelectionState,
	useReactTable,
} from "@tanstack/react-table";
import type React from "react";
import { useCallback, useState } from "react";
import { type Flow, useDeleteFlowById } from "@/api/flows";
import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icons";
import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { TagsInput } from "@/components/ui/tags-input";
import { pluralize } from "@/utils";
import { columns } from "./columns";

const FLOW_SORT_OPTIONS = [
	{ label: "A to Z", value: "NAME_ASC" },
	{ label: "Z to A", value: "NAME_DESC" },
	{ label: "Created", value: "CREATED_DESC" },
] as const;

type FlowSortValue = "NAME_ASC" | "NAME_DESC" | "CREATED_DESC" | "UPDATED_DESC";

export default function FlowsTable({
	flows,
	count,
	pageCount,
	sort,
	pagination,
	onPaginationChange,
	onSortChange,
	columnFilters,
	onColumnFiltersChange,
	onPrefetchPage,
}: {
	flows: Flow[];
	count: number;
	pageCount: number;
	sort: FlowSortValue;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onSortChange: (sort: FlowSortValue) => void;
	columnFilters: ColumnFiltersState;
	onColumnFiltersChange: (columnFilters: ColumnFiltersState) => void;
	onPrefetchPage?: (page: number) => void;
}) {
	const { deleteFlow } = useDeleteFlowById();
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	const nameSearchValue = (columnFilters.find((filter) => filter.id === "name")
		?.value ?? "") as string;
	const tagsSearchValue = (columnFilters.find((filter) => filter.id === "tags")
		?.value ?? []) as string[];

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
			const tags = Array.isArray(e) ? e : [];
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
		columns: columns,
		data: flows,
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		pageCount,
		state: {
			rowSelection,
			pagination,
		},
		onRowSelectionChange: setRowSelection,
		onPaginationChange: handlePaginationChange,
	});

	const handleDeleteRows = () => {
		const selectedRows = Object.keys(rowSelection);

		const idsToDelete = selectedRows.map((rowId) => flows[Number(rowId)].id);

		for (const id of idsToDelete) {
			deleteFlow(id);
		}

		table.toggleAllRowsSelected(false);
	};

	return (
		<div className="h-full">
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					{Object.keys(rowSelection).length > 0 ? (
						<p className="text-sm text-muted-foreground flex items-center">
							{Object.keys(rowSelection).length} selected
							<Icon
								id="Trash2"
								className="ml-2 cursor-pointer h-4 w-4 inline"
								onClick={handleDeleteRows}
							/>
						</p>
					) : (
						<p className="text-sm text-muted-foreground">
							{count} {pluralize(count, "Flow")}
						</p>
					)}
				</div>
				<div className="sm:col-span-2 md:col-span-2 lg:col-span-3">
					<SearchInput
						placeholder="Flow names"
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
					<Select value={sort} onValueChange={onSortChange}>
						<SelectTrigger aria-label="Flow sort order" className="w-full">
							<SelectValue placeholder="Sort by" />
						</SelectTrigger>
						<SelectContent>
							{FLOW_SORT_OPTIONS.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
			</div>
			<DataTable table={table} onPrefetchPage={onPrefetchPage} />
		</div>
	);
}
