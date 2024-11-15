import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { type Table as TanstackTable, flexRender } from "@tanstack/react-table";

import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationNextButton,
	PaginationPreviousButton,
	PaginationFirstButton,
	PaginationLastButton,
} from "@/components/ui/pagination";
import { cn } from "@/lib/utils";

export function DataTable<TData>({
	table,
}: {
	table: TanstackTable<TData>;
}) {
	return (
		<>
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
						{table.getRowModel().rows?.length ? (
							table.getRowModel().rows.map((row) => (
								<TableRow
									key={row.id}
									data-state={row.getIsSelected() && "selected"}
								>
									{row.getVisibleCells().map((cell) => (
										<TableCell key={cell.id}>
											{flexRender(
												cell.column.columnDef.cell,
												cell.getContext(),
											)}
										</TableCell>
									))}
								</TableRow>
							))
						) : (
							<TableRow>
								<TableCell
									colSpan={table.getAllColumns().length}
									className="h-24 text-center"
								>
									No results.
								</TableCell>
							</TableRow>
						)}
					</TableBody>
				</Table>
			</div>
			<DataTablePagination table={table} />
		</>
	);
}

interface DataTablePaginationProps<TData> {
	table: TanstackTable<TData>;
	className?: string;
}

export function DataTablePagination<TData>({
	table,
	className,
}: DataTablePaginationProps<TData>) {
	return (
		<Pagination className={cn("justify-end", className)}>
			<PaginationContent>
				<PaginationItem>
					<PaginationFirstButton
						onClick={() => table.firstPage()}
						disabled={!table.getCanPreviousPage()}
					/>
					<PaginationPreviousButton
						onClick={() => table.previousPage()}
						disabled={!table.getCanPreviousPage()}
					/>
				</PaginationItem>
				<PaginationItem className="text-sm">
					Page {Math.ceil(table.getState().pagination.pageIndex + 1)} of{" "}
					{table.getPageCount()}
				</PaginationItem>
				<PaginationItem>
					<PaginationNextButton
						onClick={() => table.nextPage()}
						disabled={!table.getCanNextPage()}
					/>
				</PaginationItem>
				<PaginationItem>
					<PaginationLastButton
						onClick={() => table.lastPage()}
						disabled={!table.getCanNextPage()}
					/>
				</PaginationItem>
			</PaginationContent>
		</Pagination>
	);
}
