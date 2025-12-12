import type { Flow } from "@/api/flows";
import FlowsTable from "./data-table";
import { FlowsHeader } from "./flows-page-header";

type FlowSortValue = "NAME_ASC" | "NAME_DESC" | "CREATED_DESC";

type FlowsPageProps = {
	flows: Flow[];
	count: number;
	sort: FlowSortValue;
};

export default function FlowsPage({ flows, count, sort }: FlowsPageProps) {
	return (
		<div>
			<FlowsHeader />
			<FlowsTable flows={flows} count={count} sort={sort} />
		</div>
	);
}
