import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListAutomationsRelatedQuery } from "@/api/automations/automations";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { buildFLowDetailsQuery } from "@/api/flows";
import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { DeploymentDetailsPage } from "@/components/deployments/deployment-details-page";
import {
	FLOW_RUN_STATES,
	FLOW_RUN_STATES_NO_SCHEDULED,
	SORT_FILTERS,
} from "@/components/flow-runs/flow-runs-list";

/**
 * Schema for validating URL search parameters for the Deployment Details page
 * @property {"Runs" | "Upcoming" | "Parameters" | "Configuration" | "Description"} tab used designate which tab view to display
 */
const searchParams = z.object({
	tab: z
		.enum(["Runs", "Upcoming", "Parameters", "Configuration", "Description"])
		.default("Runs"),
	runs: z
		.object({
			flowRuns: z
				.object({
					name: z.string().optional(),
					state: z
						.array(z.enum(FLOW_RUN_STATES))
						.optional()
						.default(FLOW_RUN_STATES_NO_SCHEDULED)
						.catch(FLOW_RUN_STATES_NO_SCHEDULED),
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
					state: z
						.array(z.enum(FLOW_RUN_STATES))
						.optional()
						.default(["Scheduled"])
						.catch(["Scheduled"]),
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
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
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
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <DeploymentDetailsPage id={id} />;
}
