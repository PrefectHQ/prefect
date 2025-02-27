import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { Icon } from "@/components/ui/icons";
import { StatusIcon } from "@/components/ui/status-badge";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

type WorkQueueLinkProps = {
	workPoolName: string;
	workQueueName: string;
};

export const WorkQueueLink = ({
	workPoolName,
	workQueueName,
}: WorkQueueLinkProps) => {
	const { data: workQueue } = useQuery(
		buildWorkQueueDetailsQuery(workPoolName, workQueueName),
	);

	if (workQueue) {
		return (
			<div className="flex items-center gap-1 text-xs">
				Work Queue
				<Link
					to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
					params={{ workPoolName, workQueueName }}
					className="flex items-center gap-1"
				>
					<Icon id="Cpu" className="size-4" />
					{workQueueName}
				</Link>
				{workQueue.status && <StatusIcon status={workQueue.status} />}
			</div>
		);
	}

	return null;
};
