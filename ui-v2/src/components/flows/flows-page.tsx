import type { Flow } from "@/api/flows";
import FlowsTable from "./data-table";
import { FlowsHeader } from "./flows-page-header";

type FlowsPageProps = {
	flows: Flow[];
	count: number;
};

export default function FlowsPage({ flows, count }: FlowsPageProps) {
	return (
		<div>
			<FlowsHeader />
			<FlowsTable flows={flows} count={count} />
		</div>
	);
}
