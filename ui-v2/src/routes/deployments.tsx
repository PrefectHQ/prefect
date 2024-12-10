import { DeploymentsEmptyState } from "@/components/deployments/empty-state";
import { DeploymentsPageHeader } from "@/components/deployments/header";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/deployments")({
	component: RouteComponent,
});

function RouteComponent() {
	return (
		<div className="flex flex-col gap-4">
			<DeploymentsPageHeader />
			<DeploymentsEmptyState />
		</div>
	);
}
