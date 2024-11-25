import { DeploymentsEmptyState } from "@/components/ui/deployments/empty-state";
import { DeploymentsLayout } from "@/components/ui/deployments/layout";
import { useDeployments } from "@/hooks/deployments";
import { createFileRoute } from "@tanstack/react-router";
import { DeploymentsDataTable } from "@/components/ui/deployments/data-table";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";

const searchParams = z.object({
	offset: z.number().int().nonnegative().optional().default(0).catch(0),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z
		.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
		.optional()
		.default("CREATED_DESC")
		.catch("CREATED_DESC"),
});

const buildFilterBody = (search?: z.infer<typeof searchParams>) => ({
	offset: search?.offset ?? 0,
	limit: search?.limit ?? 10,
	sort: search?.sort ?? "CREATED_DESC",
});

export const Route = createFileRoute("/deployments")({
	validateSearch: zodSearchValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildFilterBody(search),
	loader: useDeployments.loader,
	wrapInSuspense: true,
});

function RouteComponent() {
	const { deployments, filteredCount, totalCount } = useDeployments();
	const hasDeployments = totalCount > 0;

	return (
		<DeploymentsLayout>
			{hasDeployments ? (
				<DeploymentsDataTable deployments={deployments} />
			) : (
				<DeploymentsEmptyState />
			)}
		</DeploymentsLayout>
	);
}
