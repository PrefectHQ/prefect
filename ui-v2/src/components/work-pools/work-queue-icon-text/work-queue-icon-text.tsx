import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type WorkQueueIconTextProps = {
	workPoolName: string;
	workQueueName: string;
};

export const WorkQueueIconText = ({
	workPoolName,
	workQueueName,
}: WorkQueueIconTextProps) => (
	<Suspense fallback={<Skeleton className="h-4 w-full" />}>
		<WorkQueueIconTextImplementation
			workPoolName={workPoolName}
			workQueueName={workQueueName}
		/>
	</Suspense>
);

const WorkQueueIconTextImplementation = ({
	workPoolName,
	workQueueName,
}: WorkQueueIconTextProps) => {
	const { data: workQueue } = useSuspenseQuery(
		buildWorkQueueDetailsQuery(workPoolName, workQueueName),
	);

	return (
		<Link
			to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
			params={{ workPoolName, workQueueName }}
			className="flex items-center gap-1"
		>
			<Icon id="ListOrdered" className="size-4" />
			{workQueue.name}
		</Link>
	);
};
