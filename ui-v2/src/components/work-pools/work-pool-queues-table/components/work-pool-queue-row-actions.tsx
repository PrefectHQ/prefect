import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { WorkPoolQueueMenu } from "@/components/work-pools/work-pool-queue-menu";
import { WorkPoolQueueToggle } from "@/components/work-pools/work-pool-queue-toggle";

type WorkPoolQueueRowActionsProps = {
	queue: WorkPoolQueue;
	onUpdate?: () => void;
};

export const WorkPoolQueueRowActions = ({
	queue,
	onUpdate,
}: WorkPoolQueueRowActionsProps) => {
	return (
		<div className="flex items-center justify-end space-x-2">
			<WorkPoolQueueToggle queue={queue} onUpdate={onUpdate} />
			<WorkPoolQueueMenu queue={queue} onUpdate={onUpdate} />
		</div>
	);
};
