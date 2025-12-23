import { Circle, Pause } from "lucide-react";
import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type DeploymentStatus = components["schemas"]["DeploymentStatus"];

type DisplayStatus = DeploymentStatus | "DISABLED";

type DeploymentStatusBadgeProps = {
	deployment: { status: DeploymentStatus | null; paused: boolean };
	className?: string;
};

const getDisplayStatus = (deployment: {
	status: DeploymentStatus | null;
	paused: boolean;
}): DisplayStatus => {
	if (deployment.paused) return "DISABLED";
	return deployment.status ?? "NOT_READY";
};

const getStatusLabel = (status: DisplayStatus): string => {
	switch (status) {
		case "READY":
			return "Ready";
		case "NOT_READY":
			return "Not Ready";
		case "DISABLED":
			return "Disabled";
	}
};

const getStatusColor = (status: DisplayStatus): string => {
	switch (status) {
		case "READY":
			return "bg-green-500";
		case "NOT_READY":
			return "bg-red-500";
		case "DISABLED":
			return "bg-gray-500";
	}
};

export const DeploymentStatusBadge = ({
	deployment,
	className,
}: DeploymentStatusBadgeProps) => {
	const displayStatus = getDisplayStatus(deployment);
	const label = getStatusLabel(displayStatus);
	const colorClass = getStatusColor(displayStatus);

	return (
		<Badge
			variant="secondary"
			className={cn("flex items-center space-x-1", className)}
		>
			{displayStatus === "DISABLED" ? (
				<Pause className="h-2 w-2 text-muted-foreground" />
			) : (
				<Circle className={cn("h-2 w-2 fill-current", colorClass)} />
			)}
			<span>{label}</span>
		</Badge>
	);
};
