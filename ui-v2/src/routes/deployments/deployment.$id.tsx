import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { buildListAutomationsRelatedQuery } from "@/api/automations/automations";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { categorizeError } from "@/api/error-utils";
import { buildFLowDetailsQuery } from "@/api/flows";
import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { DeploymentDetailsPage } from "@/components/deployments/deployment-details-page";
import { SORT_FILTERS } from "@/components/flow-runs/flow-runs-list";
import { STATE_TYPES } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter-utils";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

/**
 * Schema for validating URL search parameters for the Deployment Details page
 * @property {"Details" | "Runs" | "Upcoming" | "Parameters" | "Configuration" | "Description"} tab used designate which tab view to display
 *
 * Defaults to "Details" to match V1 behavior: on narrow viewports where the
 * details sidebar is collapsed, the Details tab is the initial view. On wide
 * viewports where the details sidebar is visible, DeploymentDetailsTabs
 * redirects "Details" to "Runs" so users don't see duplicate content.
 */
const searchParams = z.object({
	tab: z
		.enum([
			"Details",
			"Runs",
			"Upcoming",
			"Parameters",
			"Configuration",
			"Description",
		])
		.default("Details"),
	runs: z
		.object({
			flowRuns: z
				.object({
					name: z.string().optional(),
					state: z.array(z.string()).optional(),
					stateTypes: z.array(z.enum(STATE_TYPES)).optional(),
				})
				.optional(),
			page: z.number().int().positive().optional().default(1).catch(1),
			limit: z.number().int().positive().optional().default(10).catch(10),
			sort: z
				.enum(SORT_FILTERS)
				.optional()
				.default("START_TIME_DESC")
				.catch("START_TIME_DESC"),
		})
		.optional(),
	upcoming: z
		.object({
			flowRuns: z
				.object({
					name: z.string().optional(),
					state: z.array(z.string()).optional(),
					stateTypes: z.array(z.enum(STATE_TYPES)).optional(),
				})
				.optional(),
			page: z.number().int().positive().optional().default(1).catch(1),
			limit: z.number().int().positive().optional().default(5).catch(5),
			sort: z
				.enum(SORT_FILTERS)
				.optional()
				.default("START_TIME_ASC")
				.catch("START_TIME_ASC"),
		})
		.optional(),
});

export type DeploymentDetailsTabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/deployments/deployment/$id")({
	validateSearch: searchParams,
	component: function RouteComponent() {
		const { id } = Route.useParams();
		return <DeploymentDetailsPage id={id} />;
	},
	loader: async ({ params, context: { queryClient } }) => {
		// ----- Critical data
		const res = await queryClient.ensureQueryData(
			buildDeploymentDetailsQuery(params.id),
		);

		// ----- Deferred data
		void queryClient.prefetchQuery(
			buildListAutomationsRelatedQuery(`prefect.deployment.${params.id}`),
		);

		void queryClient.prefetchQuery(buildFLowDetailsQuery(res.flow_id));

		if (res.work_pool_name && res.work_queue_name) {
			void queryClient.prefetchQuery(
				buildWorkQueueDetailsQuery(res.work_pool_name, res.work_queue_name),
			);
		}
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	errorComponent: function DeploymentErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load deployment");
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Deployment</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
