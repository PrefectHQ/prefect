import type { components } from "@/api/prefect";
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
import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";

import { useSet } from "@/hooks/use-set";
import { useState } from "react";
import { columns } from "./columns";

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
					<Icon id="ChevronDown" className="h-4 w-4 shrink-0" />
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

const SortComponent = () => {
	const navigate = useNavigate();

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline">
					Sort <Icon id="ChevronDown" className="ml-2 h-4 w-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				<DropdownMenuItem
					onClick={() =>
						void navigate({
							to: ".",
							search: (prev) => ({ ...prev, sort: "NAME_ASC" }),
						})
					}
				>
					A to Z
				</DropdownMenuItem>
				<DropdownMenuItem
					onClick={() =>
						void navigate({
							to: ".",
							search: (prev) => ({ ...prev, sort: "NAME_DESC" }),
						})
					}
				>
					Z to A
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};

export default function FlowsTable({
	flows,
}: {
	flows: components["schemas"]["Flow"][];
}) {
	const table = useReactTable({
		columns: columns,
		data: flows,
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		initialState: {
			pagination: {
				pageIndex: 0,
				pageSize: 10,
			},
		},
	});

	return (
		<div className="h-full">
			<header className="mb-2 flex flex-row justify-between">
				<SearchComponent />
				<div className="flex space-x-4">
					<FilterComponent />
					<SortComponent />
				</div>
			</header>
			<DataTable table={table} />
		</div>
	);
}
