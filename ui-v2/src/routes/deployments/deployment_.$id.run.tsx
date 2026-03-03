import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { categorizeError } from "@/api/error-utils";
import { buildFilterWorkPoolWorkQueuesQuery } from "@/api/work-queues";
import { CustomRunPage } from "@/components/deployments/custom-run-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

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
	component: function RouteComponent() {
		const { id } = Route.useParams();
		const search = Route.useSearch();
		return <CustomRunPage id={id} overrideParameters={search?.parameters} />;
	},
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
	pendingComponent: PrefectLoading,
	errorComponent: function DeploymentRunErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load deployment");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Run Deployment</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
