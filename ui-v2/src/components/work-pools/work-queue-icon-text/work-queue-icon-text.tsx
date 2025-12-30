import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildWorkQueueDetailsQuery, type WorkQueue } from "@/api/work-queues";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusIcon } from "@/components/ui/status-badge";

type WorkQueueIconTextBaseProps = {
	workPoolName: string;
	workQueueName: string;
	showLabel?: boolean;
	showStatus?: boolean;
	className?: string;
	iconSize?: number;
};

type WorkQueueIconTextProps = WorkQueueIconTextBaseProps;

export const WorkQueueIconText = ({
	workPoolName,
	workQueueName,
	showLabel = false,
	showStatus = false,
	className,
	iconSize,
}: WorkQueueIconTextProps) => (
	<Suspense fallback={<Skeleton className="h-4 w-full" />}>
		<WorkQueueIconTextFetched
			workPoolName={workPoolName}
			workQueueName={workQueueName}
			showLabel={showLabel}
			showStatus={showStatus}
			className={className}
			iconSize={iconSize}
		/>
	</Suspense>
);

const WorkQueueIconTextFetched = ({
	workPoolName,
	workQueueName,
	showLabel,
	showStatus,
	className,
	iconSize,
}: WorkQueueIconTextBaseProps) => {
	const { data: workQueue } = useSuspenseQuery(
		buildWorkQueueDetailsQuery(workPoolName, workQueueName),
	);

	return (
		<WorkQueueIconTextPresentational
			workQueue={workQueue}
			workPoolName={workPoolName}
			showLabel={showLabel}
			showStatus={showStatus}
			className={className}
			iconSize={iconSize}
		/>
	);
};

type WorkQueueIconTextPresentationalProps = {
	workQueue: WorkQueue;
	workPoolName: string;
	showLabel?: boolean;
	showStatus?: boolean;
	className?: string;
	iconSize?: number;
};

const WorkQueueIconTextPresentational = ({
	workQueue,
	workPoolName,
	showLabel = false,
	showStatus = false,
	className,
	iconSize,
}: WorkQueueIconTextPresentationalProps) => {
	return (
		<div className="flex items-center gap-1 text-xs">
			{showLabel && <span>Work Queue</span>}
			<Link
				to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
				params={{ workPoolName, workQueueName: workQueue.name }}
				className={className ?? "flex items-center gap-1"}
			>
				<Icon
					id="ListOrdered"
					size={iconSize}
					className={iconSize ? undefined : "size-4"}
				/>
				{workQueue.name}
			</Link>
			{showStatus && workQueue.status && (
				<StatusIcon status={workQueue.status} />
			)}
		</div>
	);
};
