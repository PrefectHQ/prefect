import { DeploymentsEmptyState } from "@/components/deployments/empty-state";
import { DeploymentsLayout } from "@/components/deployments/layout";
import { useDeployments } from "@/hooks/deployments";
import { createFileRoute } from "@tanstack/react-router";
import { DeploymentsDataTable } from "@/components/deployments/data-table";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import { useFlows } from "@/hooks/flows";
import type { PaginationState } from "@tanstack/react-table";
import { useCallback, useMemo } from "react";

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
	loader: async (deps) => {
		const { context } = deps;
		const [deployments] = await useDeployments.loader(deps);
		const flowIds = deployments?.map((d) => d.flow_id).sort();

		await useFlows.loader({
			deps: {
				offset: 0,
				sort: "CREATED_DESC",
				flows: { operator: "and_", id: { any_: flowIds } },
			},
			context,
		});
	},
});

function RouteComponent() {
	const search = Route.useSearch();

	const { deployments, filteredCount, totalCount } = useDeployments(
		buildFilterBody(search),
	);
	const flowIds = deployments?.map((d) => d.flow_id).sort();
	const { flows } = useFlows(
		{
			offset: 0,
			sort: "CREATED_DESC",
			flows: { operator: "and_", id: { any_: flowIds } },
		},
		flowIds.length > 0,
	);
	const hasDeployments = totalCount > 0;

	const deploymentsWithFlowName = deployments.map((d) => ({
		...d,
		flowName: flows.find((f) => f.id === d.flow_id)?.name ?? "",
	}));

	const [pagination, onPaginationChange] = usePagination();

	return (
		<DeploymentsLayout>
			{hasDeployments ? (
				<DeploymentsDataTable
					deployments={deploymentsWithFlowName}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					currentDeploymentCount={filteredCount}
				/>
			) : (
				<DeploymentsEmptyState />
			)}
		</DeploymentsLayout>
	);
}

const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pageIndex = search.offset ? Math.ceil(search.offset / search.limit) : 0;
	const pageSize = search.limit ?? 10;
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex,
			pageSize,
		}),
		[pageIndex, pageSize],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					offset: newPagination.pageIndex * newPagination.pageSize,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};
