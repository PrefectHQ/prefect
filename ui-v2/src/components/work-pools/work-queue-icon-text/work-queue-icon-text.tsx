import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { Icon } from "@/components/ui/icons";
import { StatusIcon } from "@/components/ui/status-badge";

type WorkQueueIconTextProps = {
	workPoolName: string;
	workQueueName: string;
	showLabel?: boolean;
	showStatus?: boolean;
	className?: string;
	iconSize?: number;
};

export const WorkQueueIconText = ({
	workPoolName,
	workQueueName,
	showLabel = false,
	showStatus = false,
	className,
	iconSize,
}: WorkQueueIconTextProps) => {
	const { data: workQueue } = useQuery({
		...buildWorkQueueDetailsQuery(workPoolName, workQueueName),
		enabled: showStatus,
		retry: false,
	});

	return (
		<div className="flex items-center gap-1 text-xs">
			{showLabel && <span>Work Queue</span>}
			<Link
				to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
				params={{ workPoolName, workQueueName }}
				className={className ?? "flex items-center gap-1"}
			>
				<Icon
					id="ListOrdered"
					size={iconSize}
					className={iconSize ? undefined : "size-4"}
				/>
				{workQueueName}
			</Link>
			{showStatus && workQueue?.status && (
				<StatusIcon status={workQueue.status} />
			)}
		</div>
	);
};
