import { buildListAutomationsRelatedQuery } from "@/api/automations/automations";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { buildFLowDetailsQuery } from "@/api/flows";
import { DeploymentDetailsPage } from "@/components/deployments/deployment-details-page";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";

/**
 * Schema for validating URL search parameters for the Deployment Details page
 * @property {"Runs" | "Upcoming" | "Parameters" | "Configuration" | "Description"} tab used designate which tab view to display
 */
const searchParams = z.object({
	tab: z
		.enum(["Runs", "Upcoming", "Parameters", "Configuration", "Description"])
		.default("Runs"),
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
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <DeploymentDetailsPage id={id} />;
}
