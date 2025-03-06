import {
	buildCountWorkPoolsQuery,
	buildFilterWorkPoolsQuery,
} from "@/api/work-pools";
import { WorkPoolsPageHeader } from "@/components/work-pools/header";
import { WorkPoolCard } from "@/components/work-pools/work-pool-card/work-pool-card";
import { pluralize } from "@/utils";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/work-pools/")({
	component: RouteComponent,
});

function RouteComponent() {
	const { data: workPoolCount = 0 } = useQuery(buildCountWorkPoolsQuery());

	const { data: workPools = [] } = useQuery(
		buildFilterWorkPoolsQuery({
			limit: 10,
			offset: 0,
		}),
	);

	return (
		// TODO: Should we just standardize a layout for all pages?
		<div className="flex flex-col gap-4">
			<WorkPoolsPageHeader />
			<div className="flex justify-between">
				<div className="text-sm text-muted-foreground">
					{workPoolCount} {pluralize(workPoolCount, "work pool")}
				</div>
				<div className="flex gap-2">{/* Search goes here */}</div>
			</div>
			<div className="flex flex-col gap-4">
				{workPools.map((workPool) => (
					<WorkPoolCard key={workPool.id} workPool={workPool} />
				))}
			</div>
		</div>
	);
}
