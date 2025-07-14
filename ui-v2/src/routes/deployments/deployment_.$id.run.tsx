import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { buildFilterWorkPoolWorkQueuesQuery } from "@/api/work-queues";
import { CustomRunPage } from "@/components/deployments/custom-run-page";

// nb: Revisit search params to determine if we're decoding the parameters correctly. Or if there are stricter typings
// We'll know stricter types as we write more of the webapp

/**
 * Schema for validating URL search parameters for the create automation page.
 * @property actions used designate how to pre-populate the fields
 */
const searchParams = z
	.object({ parameters: z.record(z.unknown()).optional() })
	.optional();

export const Route = createFileRoute("/deployments/deployment_/$id/run")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loader: async ({ params, context: { queryClient } }) => {
		// ---- Critical data
		const res = await queryClient.ensureQueryData(
			buildDeploymentDetailsQuery(params.id),
		);

		// ---- Deferred data
		if (res.work_pool_name) {
			void queryClient.prefetchQuery(
				buildFilterWorkPoolWorkQueuesQuery({
					work_pool_name: res.work_pool_name,
				}),
			);
		}
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	const search = Route.useSearch();
	return <CustomRunPage id={id} overrideParameters={search?.parameters} />;
}
