import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildListAutomationsQuery } from "@/api/automations";
import { categorizeError } from "@/api/error-utils";
import { AutomationsHeader } from "@/components/automations/automations-header";
import { AutomationsPage } from "@/components/automations/automations-page";
import { RouteErrorState } from "@/components/ui/route-error-state";

function AutomationsErrorComponent({ error, reset }: ErrorComponentProps) {
	const serverError = categorizeError(error, "Failed to load automations");

	// Only handle API errors (server-error, client-error) at route level
	// Let network errors and unknown errors bubble up to root error component
	if (
		serverError.type !== "server-error" &&
		serverError.type !== "client-error"
	) {
		throw error;
	}

	return (
		<div className="flex flex-col gap-4">
			<AutomationsHeader />
			<RouteErrorState error={serverError} onRetry={reset} />
		</div>
	);
}

// nb: Currently there is no filtering or search params used on this page
export const Route = createFileRoute("/automations/")({
	component: AutomationsPage,
	errorComponent: AutomationsErrorComponent,
	loader: ({ context }) =>
		context.queryClient.ensureQueryData(buildListAutomationsQuery()),
	wrapInSuspense: true,
});
