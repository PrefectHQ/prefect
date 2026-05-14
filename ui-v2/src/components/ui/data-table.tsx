import {
	flexRender,
	type Header,
	type Table as TanstackTable,
} from "@tanstack/react-table";
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

const shouldIgnoreRowClick = (target: EventTarget | null) =>
	target instanceof Element &&
	target.closest(
		'a, button, input, select, textarea, [role="button"], [role="checkbox"], [role="menuitem"], [role="switch"], [data-row-click-ignore="true"]',
	);

function ColumnResizeHandle<TData, TValue>({
	header,
}: {
	header: Header<TData, TValue>;
}) {
	const isResizing = header.column.getIsResizing();
	return (
		<div
			aria-hidden="true"
			data-row-click-ignore="true"
			data-testid={`column-resize-handle-${header.column.id}`}
			data-resizing={isResizing ? "true" : undefined}
			onMouseDown={header.getResizeHandler()}
			onTouchStart={header.getResizeHandler()}
			onDoubleClick={() => header.column.resetSize()}
			className={cn(
				"absolute right-0 top-0 h-full w-1 cursor-col-resize touch-none select-none bg-transparent hover:bg-primary/50",
				isResizing && "bg-primary",
			)}
			style={{ transform: "translateX(50%)" }}
		/>
	);
}

export function DataTable<TData>({
	table,
	onPrefetchPage,
	onRowClick,
}: {
	table: TanstackTable<TData>;
	onPrefetchPage?: (page: number) => void;
	onRowClick?: (row: TData) => void;
}) {
	return (
		<div className="flex flex-col gap-4">
			<div className="rounded-md border overflow-x-auto">
				<Table>
					<TableHeader>
						{table.getHeaderGroups().map((headerGroup) => (
							<TableRow key={headerGroup.id}>
								{headerGroup.headers.map((header) => {
									const canResize =
										table.options.enableColumnResizing === true &&
										header.column.getCanResize();
									const size = header.getSize();
									const maxSize = header.column.columnDef.maxSize;
									const hasExplicitSize =
										header.column.columnDef.size !== undefined ||
										table.getState().columnSizing[header.column.id] !==
											undefined;
									return (
										<TableHead
											key={header.id}
											style={{
												...(maxSize &&
													!canResize && {
														maxWidth: `${maxSize}px`,
													}),
												...(hasExplicitSize && {
													width: `${size}px`,
												}),
												...(canResize && { position: "relative" }),
											}}
										>
											{header.isPlaceholder
												? null
												: flexRender(
														header.column.columnDef.header,
														header.getContext(),
													)}
											{canResize ? (
												<ColumnResizeHandle header={header} />
											) : null}
										</TableHead>
									);
								})}
							</TableRow>
						))}
					</TableHeader>
					<TableBody>
						{table.getRowModel().rows?.length ? (
							table.getRowModel().rows.map((row) => (
								<TableRow
									key={row.id}
									data-state={row.getIsSelected() && "selected"}
									className={
										onRowClick ? "cursor-pointer hover:bg-muted" : undefined
									}
									onClick={
										onRowClick
											? (event) => {
													if (shouldIgnoreRowClick(event.target)) return;
													onRowClick(row.original);
												}
											: undefined
									}
								>
									{row.getVisibleCells().map((cell) => {
										const canResize =
											table.options.enableColumnResizing === true &&
											cell.column.getCanResize();
										const size = cell.column.getSize();
										const maxSize = cell.column.columnDef.maxSize;
										const hasExplicitSize =
											cell.column.columnDef.size !== undefined ||
											table.getState().columnSizing[cell.column.id] !==
												undefined;
										return (
											<TableCell
												key={cell.id}
												style={{
													...(maxSize &&
														!canResize && {
															maxWidth: `${maxSize}px`,
														}),
													...(hasExplicitSize && {
														width: `${size}px`,
													}),
													...(canResize && {
														maxWidth: `${size}px`,
														overflow: "hidden",
														textOverflow: "ellipsis",
													}),
												}}
											>
												{flexRender(
													cell.column.columnDef.cell,
													cell.getContext(),
												)}
											</TableCell>
										);
									})}
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
					Page {currentPage.toLocaleString()} of {totalPages.toLocaleString()}
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
