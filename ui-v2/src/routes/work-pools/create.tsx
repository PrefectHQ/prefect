import { createFileRoute } from "@tanstack/react-router";
import { buildListWorkersQuery } from "@/api/workers";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { WorkPoolCreateWizard } from "@/components/work-pools/create/work-pool-create-wizard";

export const Route = createFileRoute("/work-pools/create")({
	component: RouteComponent,
	loader: async ({ context: { queryClient } }) => {
		// Prefetch workers data for the wizard
		await queryClient.prefetchQuery(buildListWorkersQuery());
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	return (
		<div className="container mx-auto">
			<div className="mb-8">
				<Breadcrumb className="mb-4">
					<BreadcrumbList>
						<BreadcrumbItem>
							<BreadcrumbLink
								to="/work-pools"
								className="text-xl font-semibold"
							>
								Work pools
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
						<BreadcrumbItem>
							<BreadcrumbPage className="text-xl font-semibold">
								Create
							</BreadcrumbPage>
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
			<WorkPoolCreateWizard />
		</div>
	);
}
