import { Circle, Pause } from "lucide-react";
import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type DeploymentStatus = components["schemas"]["DeploymentStatus"];

type DeploymentStatusBadgeProps = {
	deployment: { status: DeploymentStatus | null; paused: boolean };
	className?: string;
};

const getStatusLabel = (status: DeploymentStatus): string => {
	switch (status) {
		case "READY":
			return "Ready";
		case "NOT_READY":
			return "Not Ready";
	}
};

const getStatusColor = (status: DeploymentStatus): string => {
	switch (status) {
		case "READY":
			return "bg-green-500";
		case "NOT_READY":
			return "bg-red-500";
	}
};

export const DeploymentStatusBadge = ({
	deployment,
	className,
}: DeploymentStatusBadgeProps) => {
	const isDisabled = deployment.paused;
	const status: DeploymentStatus = deployment.status ?? "NOT_READY";

	if (isDisabled) {
		return (
			<Badge
				variant="secondary"
				className={cn("flex items-center space-x-1", className)}
			>
				<Pause className="h-2 w-2 text-muted-foreground" />
				<span>Paused</span>
			</Badge>
		);
	}

	return (
		<Badge
			variant="secondary"
			className={cn("flex items-center space-x-1", className)}
		>
			<Circle className={cn("h-2 w-2 fill-current", getStatusColor(status))} />
			<span>{getStatusLabel(status)}</span>
		</Badge>
	);
};
