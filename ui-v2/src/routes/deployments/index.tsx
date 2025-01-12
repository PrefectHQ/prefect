import {
	type DeploymentsPaginationFilter,
	buildCountDeploymentsQuery,
	buildPaginateDeploymentsQuery,
} from "@/api/deployments";
import { buildListFlowsQuery } from "@/api/flows";
import { DeploymentsDataTable } from "@/components/deployments/data-table";
import { DeploymentsEmptyState } from "@/components/deployments/empty-state";
import { DeploymentsPageHeader } from "@/components/deployments/header";
import { useQuery, useSuspenseQueries } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import type { PaginationState } from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
/**
 * Schema for validating URL search parameters for the variables page.
 * @property {number} page - The page number to display. Must be positive. Defaults to 1.
 * @property {number} limit - The maximum number of items to return. Must be positive. Defaults to 10.
 */
const searchParams = z.object({
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

/**
 * Builds pagination parameters for deployments query from search params
 *
 * @param search - Optional validated search parameters containing page and limit
 * @returns DeploymentsPaginationFilter with page, limit and sort order
 *
 * @example
 * ```ts
 * const filter = buildPaginationBody({ page: 2, limit: 25 })
 * // Returns { page: 2, limit: 25, sort: "NAME_ASC" }
 * ```
 */
const buildPaginationBody = (
	search?: z.infer<typeof searchParams>,
): DeploymentsPaginationFilter => ({
	page: search?.page ?? 1,
	limit: search?.limit ?? 10,
	sort: "NAME_ASC",
});

export const Route = createFileRoute("/deployments/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildPaginationBody(search),
	loader: async ({ deps, context }) => {
		// Get full count of deployments, don't block the UI
		const deploymentsCountResult = context.queryClient.ensureQueryData(
			buildCountDeploymentsQuery(),
		);

		// Get paginated deployments, wait for the result to get corresponding flows
		const deploymentsPaginateResult = await context.queryClient.ensureQueryData(
			buildPaginateDeploymentsQuery(deps),
		);

		const deployments = deploymentsPaginateResult?.results ?? [];

		const flowIds = [
			...new Set(deployments.map((deployment) => deployment.flow_id)),
		];

		// Get flows corresponding to the deployments
		const flowsFilterResult = context.queryClient.ensureQueryData(
			buildListFlowsQuery({
				flows: {
					operator: "and_",
					id: {
						any_: flowIds,
					},
				},
				offset: 0,
				sort: "NAME_ASC",
			}),
		);

		return {
			deploymentsCountResult,
			deploymentsPaginateResult,
			flowsFilterResult,
		};
	},
	wrapInSuspense: true,
});

/**
 * Hook to manage pagination state and navigation for deployments table
 *
 * Handles conversion between 1-based page numbers in the URL and 0-based indices used by React Table.
 * Updates the URL search parameters when pagination changes.
 *
 * @returns A tuple containing:
 * - pagination: Current pagination state with pageIndex and pageSize
 * - onPaginationChange: Callback to update pagination and navigate with new search params
 */
const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	// React Table uses 0-based pagination, so we need to subtract 1 from the page number
	const pageIndex = (search.page ?? 1) - 1;
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
					page: newPagination.pageIndex + 1,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

function RouteComponent() {
	const search = Route.useSearch();
	const [pagination, onPaginationChange] = usePagination();

	const [{ data: deploymentsCount }, { data: deploymentsPage }] =
		useSuspenseQueries({
			queries: [
				buildCountDeploymentsQuery(),
				buildPaginateDeploymentsQuery(buildPaginationBody(search)),
			],
		});

	const deployments = deploymentsPage?.results ?? [];

	const { data: flows } = useQuery(
		buildListFlowsQuery({
			flows: {
				operator: "and_",
				id: {
					any_: [
						...new Set(deployments.map((deployment) => deployment.flow_id)),
					],
				},
			},
			offset: 0,
			sort: "NAME_ASC",
		}),
	);

	const deploymentsWithFlows = deployments.map((deployment) => ({
		...deployment,
		flow: flows?.find((flow) => flow.id === deployment.flow_id),
	}));

	return (
		<div className="flex flex-col gap-4">
			<DeploymentsPageHeader />
			{deploymentsCount === 0 ? (
				<DeploymentsEmptyState />
			) : (
				<DeploymentsDataTable
					deployments={deploymentsWithFlows}
					pageCount={deploymentsPage?.pages ?? 0}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					// TODO: Replace console.log with actual handlers for deployment actions
					onQuickRun={(deployment) => console.log(deployment)}
					onCustomRun={(deployment) => console.log(deployment)}
					onEdit={(deployment) => console.log(deployment)}
					onDelete={(deployment) => console.log(deployment)}
					onDuplicate={(deployment) => console.log(deployment)}
				/>
			)}
		</div>
	);
}
