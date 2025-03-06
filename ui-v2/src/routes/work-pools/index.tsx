import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
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
		<div>
			<h1>Work Pools</h1>
			<pre>{JSON.stringify(workPools, null, 2)}</pre>
		</div>
	);
}
