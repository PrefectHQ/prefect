import { Link } from "@tanstack/react-router";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { LateFlowRunsIndicator } from "@/components/flow-runs/late-flow-runs-indicator";
import { Badge } from "@/components/ui/badge";

type QueueNameWithLateIndicatorProps = {
	queue: WorkPoolQueue;
};

export const QueueNameWithLateIndicator = ({
	queue,
}: QueueNameWithLateIndicatorProps) => {
	const isDefault = queue.name === "default";

	// TODO: Implement proper late flow runs detection when API supports it
	// For now, using a mock count to demonstrate the feature
	const lateRunsCount =
		queue.name === "default" ? 0 : Math.floor(Math.random() * 3);

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
			{isDefault && (
				<Badge variant="secondary" className="text-xs">
					Default
				</Badge>
			)}
			<LateFlowRunsIndicator lateRunsCount={lateRunsCount} />
		</div>
	);
};
