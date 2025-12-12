import type { Flow } from "@/api/flows";
import type { PaginationState } from "@/components/flow-runs/flow-runs-list";
import FlowsTable from "./data-table";
import { FlowsHeader } from "./flows-page-header";

type FlowSortValue = "NAME_ASC" | "NAME_DESC" | "CREATED_DESC";

type FlowsPageProps = {
	flows: Flow[];
	count: number;
	pages: number;
	sort: FlowSortValue;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};

export default function FlowsPage({
	flows,
	count,
	pages,
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
				pages={pages}
				sort={sort}
				pagination={pagination}
				onPaginationChange={onPaginationChange}
			/>
		</div>
	);
}
