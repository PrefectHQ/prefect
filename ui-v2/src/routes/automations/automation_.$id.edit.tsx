import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetAutomationQuery } from "@/api/automations";
import { categorizeError } from "@/api/error-utils";
import { AutomationEditPage } from "@/components/automations/automation-edit-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

export const Route = createFileRoute("/automations/automation_/$id/edit")({
	component: function RouteComponent() {
		const { id } = Route.useParams();
		return <AutomationEditPage id={id} />;
	},
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	errorComponent: function AutomationEditErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load automation");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Edit Automation</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
