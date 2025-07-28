import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
	buildPaginateFlowRunsQuery,
	type FlowRunsPaginateFilter,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow } from "@/api/flows";

/**
 *
 * @param filter
 * @returns a simplified query object that joins a flow run's pagination data with it's parent flow
 */
export const usePaginateFlowRunswithFlows = (
	filter: FlowRunsPaginateFilter,
) => {
	const { data: paginateFlowRunsData, error: paginateFlowRunsError } = useQuery(
		buildPaginateFlowRunsQuery(filter),
	);

	const flowIds = useMemo(() => {
		if (!paginateFlowRunsData) {
			return [];
		}
		return paginateFlowRunsData.results.map((flowRun) => flowRun.flow_id);
	}, [paginateFlowRunsData]);

	const { data: flows, error: flowsError } = useQuery(
		buildListFlowsQuery(
			{
				flows: { id: { any_: flowIds }, operator: "and_" },
				offset: 0,
				sort: "CREATED_DESC",
			},
			{ enabled: flowIds.length > 0 },
		),
	);

	const flowMap = useMemo(() => {
		if (!flows) {
			return new Map<string, Flow>();
		}
		return new Map(flows.map((flow) => [flow.id, flow]));
	}, [flows]);

	// If there's no results from the query, return empty
	if (paginateFlowRunsData && paginateFlowRunsData.results.length === 0) {
		return {
			status: "success" as const,
			error: null,
			data: {
				...paginateFlowRunsData,
				results: [] satisfies Array<FlowRunWithFlow>,
			},
		};
	}

	if (paginateFlowRunsData && flowMap.size > 0) {
		return {
			status: "success" as const,
			error: null,
			data: {
				...paginateFlowRunsData,
				results: paginateFlowRunsData.results.map((flowRun) => {
					const flow = flowMap.get(flowRun.flow_id);
					return {
						...flowRun,
						flow,
					};
				}),
			},
		};
	}

	if (paginateFlowRunsError || flowsError) {
		return {
			status: "error" as const,
			error: paginateFlowRunsError || flowsError,
			data: undefined,
		};
	}

	return {
		status: "pending" as const,
		error: null,
		data: undefined,
	};
};
