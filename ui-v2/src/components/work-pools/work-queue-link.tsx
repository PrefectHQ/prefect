import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusIcon } from "@/components/ui/status-badge";

type WorkQueueLinkProps = {
	workPoolName: string;
	workQueueName: string;
};

export const WorkQueueLink = ({
	workPoolName,
	workQueueName,
}: WorkQueueLinkProps) => {
	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<WorkQueueLinkImplementation
				workPoolName={workPoolName}
				workQueueName={workQueueName}
			/>
		</Suspense>
	);
};

const WorkQueueLinkImplementation = ({
	workPoolName,
	workQueueName,
}: WorkQueueLinkProps) => {
	const { data: workQueue } = useSuspenseQuery(
		buildWorkQueueDetailsQuery(workPoolName, workQueueName),
	);

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
};
