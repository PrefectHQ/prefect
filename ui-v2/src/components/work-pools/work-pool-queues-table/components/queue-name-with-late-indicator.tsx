import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { buildCountFlowRunsQuery } from "@/api/flow-runs";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { LateFlowRunsIndicator } from "@/components/flow-runs/late-flow-runs-indicator";

type QueueNameWithLateIndicatorProps = {
	queue: WorkPoolQueue;
};

export const QueueNameWithLateIndicator = ({
	queue,
}: QueueNameWithLateIndicatorProps) => {
	const { data: lateRunsCount = 0 } = useQuery(
		buildCountFlowRunsQuery(
			{
				work_pools: {
					operator: "and_",
					name: { any_: [queue.work_pool_name || ""] },
				},
				work_pool_queues: {
					operator: "and_",
					name: { any_: [queue.name] },
				},
				flow_runs: {
					operator: "and_",
					state: {
						operator: "and_",
						name: { any_: ["Late"] },
					},
				},
			},
			30000,
		),
	);

	return (
		<div className="flex items-center space-x-2">
			<Link
				to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
				params={{
					workPoolName: queue.work_pool_name || "",
					workQueueName: queue.name,
				}}
				className="font-medium text-blue-600 hover:text-blue-800"
			>
				{queue.name}
			</Link>
			<LateFlowRunsIndicator lateRunsCount={lateRunsCount} />
		</div>
	);
};
