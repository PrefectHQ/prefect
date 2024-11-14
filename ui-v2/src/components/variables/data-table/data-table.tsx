import type { components } from "@/api/prefect";
import {
	useReactTable,
	getCoreRowModel,
	createColumnHelper,
	type PaginationState,
	type OnChangeFn,
} from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { ActionsCell } from "./cells";

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

export const VariablesDataTable = ({
	variables,
	totalVariableCount,
	pagination,
	onPaginationChange,
}: {
	variables: components["schemas"]["Variable"][];
	totalVariableCount: number;
	pagination: PaginationState;
	onPaginationChange: OnChangeFn<PaginationState>;
}) => {
	const table = useReactTable({
		data: variables,
		columns: columns,
		state: {
			pagination,
		},
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		onPaginationChange: onPaginationChange,
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
