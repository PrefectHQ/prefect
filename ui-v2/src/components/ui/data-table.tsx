import { flexRender, type Table as TanstackTable } from "@tanstack/react-table";
import {
	Pagination,
	PaginationContent,
	PaginationFirstButton,
	PaginationItem,
	PaginationLastButton,
	PaginationNextButton,
	PaginationPreviousButton,
} from "@/components/ui/pagination";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils";

export function DataTable<TData>({
	table,
	onPrefetchPage,
}: {
	table: TanstackTable<TData>;
	onPrefetchPage?: (page: number) => void;
}) {
	return (
		<div className="flex flex-col gap-4">
			<div className="rounded-md border">
				<Table>
					<TableHeader>
						{table.getHeaderGroups().map((headerGroup) => (
							<TableRow key={headerGroup.id}>
								{headerGroup.headers.map((header) => (
									<TableHead
										key={header.id}
										style={{
											...(header.column.columnDef.maxSize && {
												maxWidth: `${header.column.columnDef.maxSize}px`,
											}),
											...(header.column.columnDef.size && {
												width: `${header.column.columnDef.size}px`,
											}),
										}}
									>
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
										<TableCell
											key={cell.id}
											style={{
												...(cell.column.columnDef.maxSize && {
													maxWidth: `${cell.column.columnDef.maxSize}px`,
												}),
												...(cell.column.columnDef.size && {
													width: `${cell.column.columnDef.size}px`,
												}),
											}}
										>
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
			<div className="flex flex-row justify-between items-center">
				<DataTablePageSize table={table} />
				<DataTablePagination table={table} onPrefetchPage={onPrefetchPage} />
			</div>
		</div>
	);
}

interface DataTablePageSizeProps<TData> {
	table: TanstackTable<TData>;
}

function DataTablePageSize<TData>({ table }: DataTablePageSizeProps<TData>) {
	return (
		<div className="flex flex-row items-center gap-2 text-xs text-muted-foreground">
			<span className="whitespace-nowrap">Items per page</span>
			<Select
				value={table.getState().pagination.pageSize.toString()}
				onValueChange={(value) => {
					table.setPageSize(Number(value));
				}}
			>
				<SelectTrigger aria-label="Items per page">
					<SelectValue placeholder="Theme" />
				</SelectTrigger>
				<SelectContent>
					<SelectItem value="5">5</SelectItem>
					<SelectItem value="10">10</SelectItem>
					<SelectItem value="25">25</SelectItem>
					<SelectItem value="50">50</SelectItem>
				</SelectContent>
			</Select>
		</div>
	);
}

interface DataTablePaginationProps<TData> {
	table: TanstackTable<TData>;
	className?: string;
	onPrefetchPage?: (page: number) => void;
}

export function DataTablePagination<TData>({
	table,
	className,
	onPrefetchPage,
}: DataTablePaginationProps<TData>) {
	const totalPages = table.getPageCount();
	const currentPage = Math.min(
		Math.ceil(table.getState().pagination.pageIndex + 1),
		totalPages,
	);

	const handlePrefetchFirstPage = () => {
		if (currentPage > 1) onPrefetchPage?.(1);
	};
	const handlePrefetchPreviousPage = () => {
		if (currentPage > 1) onPrefetchPage?.(currentPage - 1);
	};
	const handlePrefetchNextPage = () => {
		if (currentPage < totalPages) onPrefetchPage?.(currentPage + 1);
	};
	const handlePrefetchLastPage = () => {
		if (currentPage < totalPages) onPrefetchPage?.(totalPages);
	};

	return (
		<Pagination className={cn("justify-end", className)}>
			<PaginationContent>
				<PaginationItem>
					<PaginationFirstButton
						onClick={() => table.firstPage()}
						onMouseEnter={handlePrefetchFirstPage}
						disabled={!table.getCanPreviousPage()}
					/>
					<PaginationPreviousButton
						onClick={() => table.previousPage()}
						onMouseEnter={handlePrefetchPreviousPage}
						disabled={!table.getCanPreviousPage()}
					/>
				</PaginationItem>
				<PaginationItem className="text-sm">
					Page {currentPage} of {totalPages}
				</PaginationItem>
				<PaginationItem>
					<PaginationNextButton
						onClick={() => table.nextPage()}
						onMouseEnter={handlePrefetchNextPage}
						disabled={!table.getCanNextPage()}
					/>
				</PaginationItem>
				<PaginationItem>
					<PaginationLastButton
						onClick={() => table.lastPage()}
						onMouseEnter={handlePrefetchLastPage}
						disabled={!table.getCanNextPage()}
					/>
				</PaginationItem>
			</PaginationContent>
		</Pagination>
	);
}
