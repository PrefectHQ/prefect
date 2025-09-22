import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type WorkerStatus = components["schemas"]["WorkerStatus"];

type WorkerStatusBadgeProps = {
	status: WorkerStatus;
	className?: string;
};

const statusConfig = {
	ONLINE: {
		label: "Online",
		color: "bg-green-500",
	},
	OFFLINE: {
		label: "Offline",
		color: "bg-red-500",
	},
} as const satisfies Record<WorkerStatus, { label: string; color: string }>;

export const WorkerStatusBadge = ({
	status,
	className,
}: WorkerStatusBadgeProps) => {
	const config = statusConfig[status];

	return (
		<Badge
			variant="secondary"
			className={cn("flex items-center space-x-1", className)}
		>
			<div className={cn("h-2 w-2 rounded-full", config.color)} />
			<span>{config.label}</span>
		</Badge>
	);
};
