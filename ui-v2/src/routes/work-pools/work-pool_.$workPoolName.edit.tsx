import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetWorkPoolQuery } from "@/api/work-pools/work-pools";

export const Route = createFileRoute(
	"/work-pools/work-pool_/$workPoolName/edit",
)({
	component: RouteComponent,
	loader: async ({ context, params }) => {
		const { workPoolName } = params;
		return context.queryClient.ensureQueryData(
			buildGetWorkPoolQuery(workPoolName),
		);
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { workPoolName } = Route.useParams();
	const { data: workPool } = useSuspenseQuery(
		buildGetWorkPoolQuery(workPoolName),
	);

	return <div>Editing work pool: {workPool.name}</div>;
}
