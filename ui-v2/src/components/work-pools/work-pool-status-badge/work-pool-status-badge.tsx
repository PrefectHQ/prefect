import { Pause } from "lucide-react";
import type { WorkPoolStatus } from "@/api/work-pools";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type WorkPoolStatusBadgeProps = {
	status: WorkPoolStatus;
	className?: string;
};

const getStatusLabel = (status: WorkPoolStatus): string => {
	switch (status) {
		case "READY":
			return "Ready";
		case "PAUSED":
			return "Paused";
		case "NOT_READY":
			return "Not Ready";
	}
};

const getStatusColor = (status: WorkPoolStatus): string => {
	switch (status) {
		case "READY":
			return "bg-green-500";
		case "PAUSED":
			return "bg-yellow-500";
		case "NOT_READY":
			return "bg-red-500";
	}
};

export const WorkPoolStatusBadge = ({
	status,
	className,
}: WorkPoolStatusBadgeProps) => {
	const label = getStatusLabel(status);
	const colorClass = getStatusColor(status);

	return (
		<Badge
			variant="secondary"
			className={cn("flex items-center space-x-1", className)}
		>
			{status === "PAUSED" ? (
				<Pause className="h-2 w-2 text-muted-foreground" />
			) : (
				<div className={cn("h-2 w-2 rounded-full", colorClass)} />
			)}
			<span>{label}</span>
		</Badge>
	);
};
