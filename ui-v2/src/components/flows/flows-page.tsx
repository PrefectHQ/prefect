import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import type { Flow } from "@/api/flows";
import FlowsTable from "./data-table";
import { FlowsHeader } from "./flows-page-header";

type FlowSortValue = "NAME_ASC" | "NAME_DESC" | "CREATED_DESC" | "UPDATED_DESC";

type FlowsPageProps = {
	flows: Flow[];
	count: number;
	pageCount: number;
	sort: FlowSortValue;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onSortChange: (sort: FlowSortValue) => void;
	columnFilters: ColumnFiltersState;
	onColumnFiltersChange: (columnFilters: ColumnFiltersState) => void;
};

export default function FlowsPage({
	flows,
	count,
	pageCount,
	sort,
	pagination,
	onPaginationChange,
	onSortChange,
	columnFilters,
	onColumnFiltersChange,
}: FlowsPageProps) {
	return (
		<div>
			<FlowsHeader />
			<FlowsTable
				flows={flows}
				count={count}
				pageCount={pageCount}
				sort={sort}
				pagination={pagination}
				onPaginationChange={onPaginationChange}
				onSortChange={onSortChange}
				columnFilters={columnFilters}
				onColumnFiltersChange={onColumnFiltersChange}
			/>
		</div>
	);
}
