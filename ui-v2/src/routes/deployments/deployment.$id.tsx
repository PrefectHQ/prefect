import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";

import { DeploymentDetailsPage } from "@/components/deployments/deployment-details-page";

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
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <DeploymentDetailsPage id={id} />;
}
