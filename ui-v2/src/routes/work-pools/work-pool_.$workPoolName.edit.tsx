import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetWorkPoolQuery } from "@/api/work-pools/work-pools";
import {
	WorkPoolEditForm,
	WorkPoolEditPageHeader,
} from "@/components/work-pools/edit";

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

	return (
		<div className="container max-w-4xl py-6">
			<WorkPoolEditPageHeader workPool={workPool} />
			<WorkPoolEditForm workPool={workPool} />
		</div>
	);
}
