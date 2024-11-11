import type { components } from "@/api/prefect";
import {
	useReactTable,
	getCoreRowModel,
	getPaginationRowModel,
	createColumnHelper,
} from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "../ui/badge";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Button } from "../ui/button";
import { MoreVerticalIcon } from "lucide-react";

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
					month: "2-digit",
					day: "2-digit",
					hour: "2-digit",
					minute: "2-digit",
					second: "2-digit",
					hour12: true,
				})
				.replace(",", "");
		},
	}),
	columnHelper.accessor("tags", {
		header: "Tags",
		cell: (props) => {
			const tags = props.getValue();
			if (!tags) return null;
			return (
				<div className="flex flex-row gap-1">
					{tags?.map((tag) => (
						<Badge key={tag}>{tag}</Badge>
					))}
				</div>
			);
		},
	}),
	columnHelper.display({
		id: "actions",
		cell: ({ row }) => {
			const id = row.original.id;
			if (!id) return null;
			return (
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="ghost" className="h-8 w-8 p-0 ml-auto">
							<span className="sr-only">Open menu</span>
							<MoreVerticalIcon className="h-4 w-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
						<DropdownMenuLabel>Actions</DropdownMenuLabel>
						<DropdownMenuItem
							onClick={() => void navigator.clipboard.writeText(id)}
						>
							Copy ID
						</DropdownMenuItem>
						<DropdownMenuItem
							onClick={() =>
								void navigator.clipboard.writeText(row.original.name)
							}
						>
							Copy Name
						</DropdownMenuItem>
						<DropdownMenuItem
							onClick={() => {
								const copyValue =
									typeof row.original.value !== "string"
										? JSON.stringify(row.original.value)
										: row.original.value;
								if (copyValue) {
									void navigator.clipboard.writeText(copyValue);
								}
							}}
						>
							Copy Value
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			);
		},
	}),
];

export const VariablesDataTable = ({
	variables,
}: {
	variables: components["schemas"]["Variable"][];
}) => {
	const table = useReactTable({
		data: variables,
		columns: columns,
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		initialState: {
			pagination: {
				pageIndex: 0,
				pageSize: 10,
			},
		},
	});

	return <DataTable table={table} />;
};
