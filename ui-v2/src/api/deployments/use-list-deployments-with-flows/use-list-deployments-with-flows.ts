import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
	buildPaginateDeploymentsQuery,
	type Deployment,
	type DeploymentsPaginationFilter,
} from "@/api/deployments";
import { buildListFlowsQuery, type Flow } from "@/api/flows";

export type DeploymentWithFlow = Deployment & {
	flow: Flow | undefined;
};

/**
 * A hook that is used to get a pagination list of Deployments, with flow data joined
 *
 * @returns a pagination list of deployments, joined with flow data
 *
 *  @example
 * ```tsx
function DeploymentListWithFlows() {
	const { data, status } = useListDeploymentsWithFlows();
    
	if (data) {
		return (
			<ul>
				{data.results.map((deployment) => {
					const label = deployment.flow
						? `${deployment.flow.name} > ${deployment.name}`
						: deployment.name;
					return <li key={deployment.id}>{label}</li>;
				})}
			</ul>
		);
	}

	if (status === "error") {
		return <p>Error has occurred</p>;
	}

	return <div>Loading...</div>;
}
 * ```
 */
export const useListDeploymentsWithFlows = (
	filter: DeploymentsPaginationFilter = {
		page: 1,
		limit: 100,
		sort: "NAME_ASC",
	},
) => {
	const { data: deploymentsData, status: deploymentsStatus } = useQuery(
		buildPaginateDeploymentsQuery(filter),
	);

	// Creates a set of unique flow ids
	const deploymentsFlowIds = new Set(
		deploymentsData?.results.map((deployment) => deployment.flow_id),
	);

	const { data: flowsData, status: flowsStatus } = useQuery(
		buildListFlowsQuery(
			{
				flows: {
					operator: "or_",
					id: { any_: Array.from(deploymentsFlowIds) },
				},
				sort: "NAME_DESC",
				offset: 0,
			},
			{ enabled: deploymentsFlowIds.size > 0 },
		),
	);

	return useMemo(() => {
		if (flowsData && deploymentsData) {
			const flowMap = new Map<string, Flow>(
				flowsData.map((flow) => [flow.id, flow]),
			);
			// Normalize data per deployment with deployment & flow
			const deploymentsWithFlows = deploymentsData.results.map(
				(deployment) => ({
					...deployment,
					flow: flowMap.get(deployment.flow_id),
				}),
			);

			const { count, limit, pages, page } = deploymentsData;
			const retData = {
				count,
				limit,
				pages,
				page,
				results: deploymentsWithFlows,
			};
			return {
				data: retData,
				status: "success",
			};
		}

		if (flowsStatus === "error" || deploymentsStatus === "error") {
			return {
				data: undefined,
				status: "error",
			};
		}

		return {
			data: undefined,
			status: "pending",
		};
	}, [deploymentsData, deploymentsStatus, flowsData, flowsStatus]);
};
