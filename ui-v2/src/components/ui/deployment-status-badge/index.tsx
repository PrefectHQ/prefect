import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { startCase, lowerCase } from "lodash-es";

type DeploymentStatusBadgeProps = {
	status: components["schemas"]["DeploymentStatus"];
};

export const DeploymentStatusBadge = ({
	status,
}: DeploymentStatusBadgeProps) => {
	const statusName = startCase(lowerCase(status));
	return (
		<Badge variant="outline">
			<span
				className="inline-block w-2 h-2 rounded-full mr-2"
				style={{
					backgroundColor: status === "READY" ? "#22c55e" : "#ef4444",
				}}
			/>
			{statusName}
		</Badge>
	);
};
