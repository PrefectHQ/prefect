import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	type RowSelectionState,
	useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";
import { type Flow, useDeleteFlowById } from "@/api/flows";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { useSet } from "@/hooks/use-set";
import { columns } from "./columns";
import { TableCountHeader } from "./table-count-header";

const SearchComponent = () => {
	const navigate = useNavigate();

	return (
		<div className="relative">
			<Input
				placeholder="Flow names"
				className="pl-10"
				onChange={(e) =>
					void navigate({
						to: ".",
						search: (prev) => ({ ...prev, name: e.target.value }),
					})
				}
			/>
			<Icon
				id="Search"
				className="absolute left-3 top-2.5 text-muted-foreground"
				size={18}
			/>
		</div>
	);
};
const FilterComponent = () => {
	const [selectedTags, selectedTagsUtils] = useSet<string>();
	const [open, setOpen] = useState(false);

	const renderSelectedTags = () => {
		if (selectedTags.size === 0) return "All tags";
		if (selectedTags.size === 1) return Array.from(selectedTags)[0];
		return `${Array.from(selectedTags)[0]}, ${Array.from(selectedTags)[1]}${selectedTags.size > 2 ? "..." : ""}`;
	};

	return (
		<DropdownMenu open={open} onOpenChange={setOpen}>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="w-[150px] justify-between">
					<span className="truncate">{renderSelectedTags()}</span>
					<Icon id="ChevronDown" className="size-4 shrink-0" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				<DropdownMenuItem
					onSelect={(e) => {
						e.preventDefault();
						selectedTagsUtils.toggle("Tag 1");
					}}
				>
					<input
						type="checkbox"
						checked={selectedTags.has("Tag 1")}
						readOnly
						className="mr-2"
					/>
					Tag 1
				</DropdownMenuItem>
				<DropdownMenuItem
					onSelect={(e) => {
						e.preventDefault();
						selectedTagsUtils.toggle("Tag 2");
					}}
				>
					<input
						type="checkbox"
						checked={selectedTags.has("Tag 2")}
						readOnly
						className="mr-2"
					/>
					Tag 2
				</DropdownMenuItem>
				<DropdownMenuItem
					onSelect={(e) => {
						e.preventDefault();
						selectedTagsUtils.toggle("Tag 3");
					}}
				>
					<input
						type="checkbox"
						checked={selectedTags.has("Tag 3")}
						readOnly
						className="mr-2"
					/>
					Tag 3
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};

const FLOW_SORT_OPTIONS = [
	{ label: "A to Z", value: "NAME_ASC" },
	{ label: "Z to A", value: "NAME_DESC" },
	{ label: "Created", value: "CREATED_DESC" },
] as const;

type FlowSortValue = (typeof FLOW_SORT_OPTIONS)[number]["value"];

const SortComponent = ({ currentSort }: { currentSort: FlowSortValue }) => {
	const navigate = useNavigate();

	const currentLabel =
		FLOW_SORT_OPTIONS.find((opt) => opt.value === currentSort)?.label ?? "Sort";

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline">
					{currentLabel} <Icon id="ChevronDown" className="ml-2 size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				{FLOW_SORT_OPTIONS.map((option) => (
					<DropdownMenuItem
						key={option.value}
						onClick={() =>
							void navigate({
								to: ".",
								search: (prev) => ({ ...prev, sort: option.value }),
							})
						}
					>
						{option.label}
					</DropdownMenuItem>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
};

export default function FlowsTable({
	flows,
	count,
	sort,
}: {
	flows: Flow[];
	count: number;
	sort: FlowSortValue;
}) {
	const { deleteFlow } = useDeleteFlowById();
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
	const table = useReactTable({
		columns: columns,
		data: flows,
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		state: {
			rowSelection,
		},
		initialState: {
			pagination: {
				pageIndex: 0,
				pageSize: 10,
			},
		},
		onRowSelectionChange: setRowSelection,
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
			<header className="mb-2 flex flex-row justify-between">
				<TableCountHeader
					count={count}
					handleDeleteRows={handleDeleteRows}
					rowSelectionState={rowSelection}
				/>
				<div className="flex space-x-4">
					<SearchComponent />
					<FilterComponent />
					<SortComponent currentSort={sort} />
				</div>
			</header>
			<DataTable table={table} />
		</div>
	);
}
