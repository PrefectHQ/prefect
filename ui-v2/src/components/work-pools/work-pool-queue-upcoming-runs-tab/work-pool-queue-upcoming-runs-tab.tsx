import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsPaginateFilter,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow } from "@/api/flows";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { FlowRunsList } from "@/components/flow-runs/flow-runs-list";
import {
	FlowRunsPagination,
	type PaginationState,
} from "@/components/flow-runs/flow-runs-list/flow-runs-pagination";

type WorkPoolQueueUpcomingRunsTabProps = {
	workPoolName: string;
	queue: WorkPoolQueue;
	className?: string;
};

export const WorkPoolQueueUpcomingRunsTab = ({
	workPoolName,
	queue,
	className,
}: WorkPoolQueueUpcomingRunsTabProps) => {
	const [pagination, setPagination] = useState<PaginationState>({
		limit: 5,
		page: 1,
	});

	const filter: FlowRunsPaginateFilter = useMemo(
		() => ({
			page: pagination.page,
			limit: pagination.limit,
			sort: "EXPECTED_START_TIME_ASC",
			work_pools: {
				operator: "and_",
				name: { any_: [workPoolName] },
			},
			work_pool_queues: {
				operator: "and_",
				name: { any_: [queue.name] },
			},
			flow_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					name: { any_: ["Scheduled"] },
				},
			},
		}),
		[workPoolName, queue.name, pagination],
	);

	const countFilter: FlowRunsCountFilter = useMemo(
		() => ({
			work_pools: {
				operator: "and_",
				name: { any_: [workPoolName] },
			},
			work_pool_queues: {
				operator: "and_",
				name: { any_: [queue.name] },
			},
			flow_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					name: { any_: ["Scheduled"] },
				},
			},
		}),
		[workPoolName, queue.name],
	);

	const { data: paginatedData } = useQuery(buildPaginateFlowRunsQuery(filter));

	const { data: totalCount } = useQuery(buildCountFlowRunsQuery(countFilter));

	const flowIds = useMemo(
		() => [
			...new Set(
				(paginatedData?.results ?? []).map((flowRun) => flowRun.flow_id),
			),
		],
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

	const flowRunsWithFlows = useMemo(() => {
		if (!paginatedData?.results) return [];
		const flowMap = new Map(flows?.map((flow: Flow) => [flow.id, flow]) ?? []);
		return paginatedData.results
			.map((flowRun) => {
				const flow = flowMap.get(flowRun.flow_id);
				if (!flow) return null;
				return {
					...flowRun,
					flow,
				};
			})
			.filter((flowRun) => flowRun !== null) as FlowRunWithFlow[];
	}, [paginatedData?.results, flows]);

	const handlePaginationChange = useCallback(
		(newPagination: PaginationState) => {
			setPagination(newPagination);
		},
		[],
	);

	if (!paginatedData || totalCount === undefined) {
		return (
			<div className={className}>
				<div className="text-muted-foreground text-center py-8">
					Loading upcoming runs...
				</div>
			</div>
		);
	}

	return (
		<div className={className}>
			<FlowRunsList flowRuns={flowRunsWithFlows} />

			{paginatedData.pages > 1 && (
				<div className="mt-6">
					<FlowRunsPagination
						count={totalCount}
						pages={paginatedData.pages}
						pagination={pagination}
						onChangePagination={handlePaginationChange}
					/>
				</div>
			)}
		</div>
	);
};
