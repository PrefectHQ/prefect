import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildListAutomationsQuery } from "@/api/automations";
import { categorizeError } from "@/api/error-utils";
import { AutomationsHeader } from "@/components/automations/automations-header";
import { AutomationsPage } from "@/components/automations/automations-page";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Skeleton component shown while the automations page is loading.
 * Displays placeholder elements for header and card-shaped skeletons.
 */
const automationsPageSkeleton = () => {
	return (
		<div className="flex flex-col gap-4">
			{/* Header skeleton */}
			<Skeleton className="h-8 w-32" />
			{/* Card skeletons */}
			{Array.from({ length: 5 }).map((_, i) => (
				<div
					key={`automation-skeleton-${String(i)}`}
					className="rounded-lg border p-4 flex flex-col gap-2"
				>
					<Skeleton className="h-5 w-48" />
					<Skeleton className="h-4 w-full" />
				</div>
			))}
		</div>
	);
};

// nb: Currently there is no filtering or search params used on this page
export const Route = createFileRoute("/automations/")({
	component: AutomationsPage,
	errorComponent: function AutomationsErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
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
	},
	loader: ({ context }) =>
		context.queryClient.ensureQueryData(buildListAutomationsQuery()),
	wrapInSuspense: true,
	pendingComponent: automationsPageSkeleton,
});
