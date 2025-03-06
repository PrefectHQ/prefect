import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import { WorkPoolsPageHeader } from "@/components/work-pools/header";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/work-pools/")({
	component: RouteComponent,
});

function RouteComponent() {
	const { data: workPools } = useQuery(
		buildFilterWorkPoolsQuery({
			limit: 10,
			offset: 0,
		}),
	);

	return (
		// TODO: Should we just standardize a layout for all pages?
		<div className="flex flex-col gap-4">
			<WorkPoolsPageHeader />
			<pre>{JSON.stringify(workPools, null, 2)}</pre>
		</div>
	);
}
