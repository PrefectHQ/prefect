import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import type { Flow } from "@/api/flows";
import { Button } from "@/components/ui/button";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import FlowsTable from "./data-table";
import { FlowsEmptyState } from "./empty-state";
import { FlowsHeader } from "./flows-page-header";

type FlowSortValue = "NAME_ASC" | "NAME_DESC" | "CREATED_DESC" | "UPDATED_DESC";

type FlowsPageProps = {
	flows: Flow[];
	count: number;
	totalCount: number;
	pageCount: number;
	sort: FlowSortValue;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onSortChange: (sort: FlowSortValue) => void;
	columnFilters: ColumnFiltersState;
	onColumnFiltersChange: (columnFilters: ColumnFiltersState) => void;
	onPrefetchPage?: (page: number) => void;
	onClearFilters: () => void;
};

export default function FlowsPage({
	flows,
	count,
	totalCount,
	pageCount,
	sort,
	pagination,
	onPaginationChange,
	onSortChange,
	columnFilters,
	onColumnFiltersChange,
	onPrefetchPage,
	onClearFilters,
}: FlowsPageProps) {
	return (
		<div className="flex flex-col gap-4">
			<FlowsHeader />
			{totalCount === 0 ? (
				<FlowsEmptyState />
			) : count === 0 ? (
				<FlowsFilteredEmptyState onClearFilters={onClearFilters} />
			) : (
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
					onPrefetchPage={onPrefetchPage}
				/>
			)}
		</div>
	);
}

const FlowsFilteredEmptyState = ({
	onClearFilters,
}: {
	onClearFilters: () => void;
}) => (
	<EmptyState>
		<EmptyStateIcon id="Search" />
		<EmptyStateTitle>No flows match your filters</EmptyStateTitle>
		<EmptyStateDescription>
			Try adjusting your search or tag filters.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button variant="outline" onClick={onClearFilters}>
				Clear filters
			</Button>
		</EmptyStateActions>
	</EmptyState>
);
