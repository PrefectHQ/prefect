import type { components } from "@/api/prefect";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import {
	type ColumnDef,
	getCoreRowModel,
	useReactTable,
	flexRender,
} from "@tanstack/react-table";
import { NameCell, TypeCell, ActionsCell, SelectCell, SelectHeaderCell } from "./cells";

type BlockDocument = components["schemas"]["BlockDocument"];

const columns: ColumnDef<BlockDocument>[] = [
	{
		id: "select",
		header: SelectHeaderCell,
		cell: SelectCell,
		enableSorting: false,
		enableHiding: false,
	},
	{
		accessorKey: "name",
		header: "Name",
		cell: NameCell,
	},
	{
		accessorKey: "type",
		header: "Type", 
		cell: TypeCell,
	},
	{
		id: "actions",
		cell: ActionsCell,
		enableSorting: false,
	},
];

export const BlocksDataTable = ({ blocks }: { blocks: BlockDocument[] }) => {
	const table = useReactTable({
		data: blocks,
		columns,
		getCoreRowModel: getCoreRowModel(),
		enableRowSelection: true,
	});

	return (
		<div className="rounded-md border">
			<Table>
				<TableHeader>
					{table.getHeaderGroups().map((headerGroup) => (
						<TableRow key={headerGroup.id}>
							{headerGroup.headers.map((header) => (
								<TableHead key={header.id}>
									{header.isPlaceholder
										? null
										: flexRender(
												header.column.columnDef.header,
												header.getContext(),
										)}
								</TableHead>
							))}
						</TableRow>
					))}
				</TableHeader>
				<TableBody>
					{table.getRowModel().rows.map((row) => (
						<TableRow key={row.id}>
							{row.getVisibleCells().map((cell) => (
								<TableCell key={cell.id}>
									{flexRender(
										cell.column.columnDef.cell,
										cell.getContext(),
									)}
								</TableCell>
							))}
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
};
