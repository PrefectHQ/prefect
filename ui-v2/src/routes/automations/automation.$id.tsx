import { createFileRoute } from "@tanstack/react-router";
import { buildGetAutomationQuery } from "@/api/automations";
import { AutomationDetailsPage } from "@/components/automations/automation-details-page";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/automations/automation/$id")({
	component: function RouteComponent() {
		const { id } = Route.useParams();
		return <AutomationDetailsPage id={id} />;
	},
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	wrapInSuspense: true,
	pendingComponent: function AutomationDetailPageSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center gap-2">
					<Skeleton className="h-4 w-24" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-48" />
				</div>
				<div className="rounded-lg border p-4 flex flex-col gap-3">
					<div className="flex items-center gap-4 py-2">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-4 w-48 ml-4" />
					</div>
					<div className="flex items-center gap-4 py-2">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-4 w-48 ml-4" />
					</div>
					<div className="flex items-center gap-4 py-2">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-4 w-48 ml-4" />
					</div>
					<div className="flex items-center gap-4 py-2">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-4 w-48 ml-4" />
					</div>
				</div>
				<div className="flex gap-2 justify-end">
					<Skeleton className="h-9 w-20" />
					<Skeleton className="h-9 w-20" />
				</div>
			</div>
		);
	},
});
