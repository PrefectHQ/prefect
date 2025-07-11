import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildFilterFlowRunsQuery, type FlowRunsFilter } from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow } from "@/api/flows";

/**
 *
 * @param filter
 * @returns a simplified query object that joins a flow run's pagination data with it's parent flow
 */
export const useFilterFlowRunswithFlows = (filter: FlowRunsFilter) => {
	const { data: flowRunsData, error: flowRunsError } = useQuery(
		buildFilterFlowRunsQuery(filter),
	);

	const flowIds = useMemo(() => {
		if (!flowRunsData) {
			return [];
		}
		return flowRunsData.map((flowRun) => flowRun.flow_id);
	}, [flowRunsData]);

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
	if (flowRunsData && flowRunsData.length === 0) {
		return {
			status: "success" as const,
			error: null,
			data: [],
		};
	}

	if (flowRunsData && flowMap.size > 0) {
		return {
			status: "success" as const,
			error: null,
			data: flowRunsData.map((flowRun) => {
				const flow = flowMap.get(flowRun.flow_id);
				return {
					...flowRun,
					flow,
				};
			}),
		};
	}

	if (flowRunsError || flowsError) {
		return {
			status: "error" as const,
			error: flowRunsError || flowsError,
			data: undefined,
		};
	}

	return {
		status: "pending" as const,
		error: null,
		data: undefined,
	};
};
