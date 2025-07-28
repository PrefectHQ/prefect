import { Badge } from "@/components/ui/badge";
import { WorkPoolStatusIcon } from "@/components/work-pools/work-pool-status-icon";
import { cn } from "@/lib/utils";
import { getWorkPoolStatusInfo, type WorkPoolStatus } from "@/lib/work-pools";

interface WorkPoolStatusBadgeProps {
	status: WorkPoolStatus;
	className?: string;
}

export const WorkPoolStatusBadge = ({
	status,
	className,
}: WorkPoolStatusBadgeProps) => {
	const statusInfo = getWorkPoolStatusInfo(status);

	return (
		<Badge
			variant="secondary"
			className={cn("flex items-center space-x-1", className)}
		>
			<WorkPoolStatusIcon
				status={status}
				showTooltip={false}
				className="h-3 w-3"
			/>
			<span>{statusInfo.label}</span>
		</Badge>
	);
};
