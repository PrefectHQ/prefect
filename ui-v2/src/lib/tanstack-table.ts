import {
	columnFilteringFeature,
	columnResizingFeature,
	columnSizingFeature,
	columnVisibilityFeature,
	createPaginatedRowModel,
	createSortedRowModel,
	createTableHook,
	type RowData,
	rowPaginationFeature,
	rowSelectionFeature,
	rowSortingFeature,
	sortFn_alphanumeric,
	sortFn_datetime,
	sortFn_text,
	type TableState,
	type CellContext as TanStackCellContext,
	type Column as TanStackColumn,
	type ColumnDef as TanStackColumnDef,
	type Header as TanStackHeader,
	type ReactTable as TanStackReactTable,
	tableFeatures,
} from "@tanstack/react-table";

const prefectTableFeatures = tableFeatures({
	columnFilteringFeature,
	columnSizingFeature,
	columnResizingFeature,
	columnVisibilityFeature,
	rowPaginationFeature,
	paginatedRowModel: createPaginatedRowModel(),
	rowSelectionFeature,
	rowSortingFeature,
	sortedRowModel: createSortedRowModel(),
	sortFns: {
		alphanumeric: sortFn_alphanumeric,
		datetime: sortFn_datetime,
		text: sortFn_text,
	},
});

const prefectTable = createTableHook({
	features: prefectTableFeatures,
	tableComponents: {},
	cellComponents: {},
	headerComponents: {},
});

export const createColumnHelper = prefectTable.createAppColumnHelper;
export const useTable = prefectTable.useAppTable;

type PrefectTableFeatures = typeof prefectTableFeatures;

export type CellContext<
	TData extends RowData,
	TValue = unknown,
> = TanStackCellContext<PrefectTableFeatures, TData, TValue>;

export type Column<TData extends RowData, TValue = unknown> = TanStackColumn<
	PrefectTableFeatures,
	TData,
	TValue
>;

export type ColumnDef<
	TData extends RowData,
	TValue = unknown,
> = TanStackColumnDef<PrefectTableFeatures, TData, TValue>;

export type Header<TData extends RowData, TValue = unknown> = TanStackHeader<
	PrefectTableFeatures,
	TData,
	TValue
>;

export type Table<TData extends RowData> = TanStackReactTable<
	PrefectTableFeatures,
	TData,
	TableState<PrefectTableFeatures>
>;
