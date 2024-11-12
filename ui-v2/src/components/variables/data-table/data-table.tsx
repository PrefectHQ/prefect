import type { components } from "@/api/prefect";
import {
	useReactTable,
	getCoreRowModel,
	createColumnHelper,
	type PaginationState,
} from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { ActionsCell } from "./cells";
import { useNavigate } from "@tanstack/react-router";

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
		cell: ActionsCell,
	}),
];

export const VariablesDataTable = ({
	variables,
	totalVariableCount,
	pagination,
}: {
	variables: components["schemas"]["Variable"][];
	totalVariableCount: number;
	pagination: PaginationState;
}) => {
	const navigate = useNavigate({ from: "/variables" });

	const table = useReactTable({
		data: variables,
		columns: columns,
		state: {
			pagination,
		},
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		onPaginationChange: (updater) => {
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					offset: newPagination.pageIndex * newPagination.pageSize,
					limit: newPagination.pageSize,
				}),
			});
		},
		rowCount: totalVariableCount,
	});

	return (
		<div className="flex flex-col gap-6 mt-2">
			<div className="flex flex-row justify-between items-center">
				<p className="text-sm text-muted-foreground">
					{totalVariableCount} Variables
				</p>
			</div>
			<DataTable table={table} />
		</div>
	);
};
