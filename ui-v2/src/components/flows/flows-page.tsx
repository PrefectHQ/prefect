import type { PaginationState } from "@tanstack/react-table";
import type { Flow } from "@/api/flows";
import FlowsTable from "./data-table";
import { FlowsHeader } from "./flows-page-header";

type FlowSortValue = "NAME_ASC" | "NAME_DESC" | "CREATED_DESC";

type FlowsPageProps = {
	flows: Flow[];
	count: number;
	pageCount: number;
	sort: FlowSortValue;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};

export default function FlowsPage({
	flows,
	count,
	pageCount,
	sort,
	pagination,
	onPaginationChange,
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
			/>
		</div>
	);
}
