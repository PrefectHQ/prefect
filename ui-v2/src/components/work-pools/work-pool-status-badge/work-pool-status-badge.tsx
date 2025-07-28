import { Badge } from "@/components/ui/badge";
import { WorkPoolStatusIcon } from "@/components/work-pools/work-pool-status-icon";
import { cn } from "@/lib/utils";
import type { WorkPoolStatus } from "../types";

export type { WorkPoolStatus };

interface WorkPoolStatusBadgeProps {
	status: WorkPoolStatus;
	className?: string;
}

const getStatusLabel = (status: WorkPoolStatus): string => {
	switch (status) {
		case "ready":
			return "Ready";
		case "paused":
			return "Paused";
		case "not_ready":
			return "Not Ready";
	}
};

export const WorkPoolStatusBadge = ({
	status,
	className,
}: WorkPoolStatusBadgeProps) => {
	const label = getStatusLabel(status);

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
			<span>{label}</span>
		</Badge>
	);
};
