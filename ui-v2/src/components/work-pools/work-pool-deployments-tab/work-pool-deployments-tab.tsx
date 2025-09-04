import { useQuery } from "@tanstack/react-query";
import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountDeploymentsQuery,
	buildPaginateDeploymentsQuery,
	type DeploymentsPaginationFilter,
} from "@/api/deployments";
import { buildListFlowsQuery } from "@/api/flows";
import type { components } from "@/api/prefect";
import { DeploymentsDataTable } from "@/components/deployments/data-table";

type WorkPoolDeploymentsTabProps = {
	workPoolName: string;
	className?: string;
};

export const WorkPoolDeploymentsTab = ({
	workPoolName,
	className,
}: WorkPoolDeploymentsTabProps) => {
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 50,
	});
	const [sort, setSort] =
		useState<components["schemas"]["DeploymentSort"]>("CREATED_DESC");
	const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

	const filter: DeploymentsPaginationFilter = useMemo(
		() => ({
			page: pagination.pageIndex + 1,
			limit: pagination.pageSize,
			sort,
			work_pools: {
				operator: "and_",
				name: { any_: [workPoolName] },
			},
			deployments: {
				operator: "and_",
				flow_or_deployment_name: {
					like_:
						(columnFilters.find((f) => f.id === "flowOrDeploymentName")
							?.value as string) ?? "",
				},
				tags: {
					operator: "and_",
					all_:
						(columnFilters.find((f) => f.id === "tags")?.value as string[]) ??
						[],
				},
			},
		}),
		[workPoolName, pagination, sort, columnFilters],
	);

	const countFilter = useMemo(
		() => ({
			offset: 0,
			sort: "CREATED_DESC" as const,
			work_pools: {
				operator: "and_" as const,
				name: { any_: [workPoolName] },
			},
		}),
		[workPoolName],
	);

	const { data: paginatedData } = useQuery(
		buildPaginateDeploymentsQuery(filter),
	);

	const { data: totalCount } = useQuery(
		buildCountDeploymentsQuery(countFilter),
	);

	const flowIds = useMemo(
		() => [...new Set((paginatedData?.results ?? []).map((d) => d.flow_id))],
		[paginatedData?.results],
	);

	const { data: flows } = useQuery(
		buildListFlowsQuery(
			{
				flows: {
					operator: "and_",
					id: { any_: flowIds },
				},
				offset: 0,
				sort: "NAME_ASC",
			},
			{ enabled: flowIds.length > 0 },
		),
	);

	const deploymentsWithFlows = useMemo(() => {
		if (!paginatedData?.results) return [];
		const flowMap = new Map(flows?.map((flow) => [flow.id, flow]) ?? []);
		return paginatedData.results.map((deployment) => ({
			...deployment,
			flow: flowMap.get(deployment.flow_id),
		}));
	}, [paginatedData?.results, flows]);

	const handlePaginationChange = useCallback(
		(newPagination: PaginationState) => {
			setPagination(newPagination);
		},
		[],
	);

	const handleSortChange = useCallback(
		(newSort: components["schemas"]["DeploymentSort"]) => {
			setSort(newSort);
		},
		[],
	);

	const handleColumnFiltersChange = useCallback(
		(newFilters: ColumnFiltersState) => {
			setColumnFilters(newFilters);
		},
		[],
	);

	// Show loading only on initial load, not on sorting/pagination changes
	if (!paginatedData || totalCount === undefined) {
		return (
			<div className={className}>
				<div className="text-muted-foreground text-center py-8">
					Loading deployments...
				</div>
			</div>
		);
	}

	return (
		<div className={className}>
			<DeploymentsDataTable
				deployments={deploymentsWithFlows}
				currentDeploymentsCount={totalCount}
				pageCount={paginatedData.pages}
				pagination={pagination}
				sort={sort}
				columnFilters={columnFilters}
				onPaginationChange={handlePaginationChange}
				onSortChange={handleSortChange}
				onColumnFiltersChange={handleColumnFiltersChange}
			/>
		</div>
	);
};
