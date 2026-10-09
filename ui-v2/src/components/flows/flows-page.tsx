import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import type { ServerError } from "@/api/error-utils";
import type { Flow } from "@/api/flows";
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
	isPending?: boolean;
	isPlaceholderData?: boolean;
	error?: ServerError;
	onRetry?: () => void;
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
	isPending = false,
	isPlaceholderData = false,
	error,
	onRetry,
}: FlowsPageProps) {
	return (
		<div className="flex flex-col gap-4">
			<FlowsHeader />
			{totalCount === 0 ? (
				<FlowsEmptyState />
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
					onClearFilters={onClearFilters}
					isPending={isPending}
					isPlaceholderData={isPlaceholderData}
					error={error}
					onRetry={onRetry}
				/>
			)}
		</div>
	);
}
