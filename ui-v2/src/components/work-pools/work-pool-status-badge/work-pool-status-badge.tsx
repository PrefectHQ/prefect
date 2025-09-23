import { Pause } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";
import type { WorkPoolStatus } from "../types";

export type { WorkPoolStatus };

type WorkPoolStatusBadgeProps = {
	status: WorkPoolStatus;
	className?: string;
};

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

const getStatusColor = (status: WorkPoolStatus): string => {
	switch (status) {
		case "ready":
			return "bg-green-500";
		case "paused":
			return "bg-yellow-500";
		case "not_ready":
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
			{status === "paused" ? (
				<Pause className="h-2 w-2 text-muted-foreground" />
			) : (
				<div className={cn("h-2 w-2 rounded-full", colorClass)} />
			)}
			<span>{label}</span>
		</Badge>
	);
};
