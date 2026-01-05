import { cva } from "class-variance-authority";
import { Circle, Pause } from "lucide-react";
import type { components } from "@/api/prefect";
import { capitalize } from "@/utils";
import { Badge } from "../badge";

type Status =
	| components["schemas"]["DeploymentStatus"]
	| components["schemas"]["WorkPoolStatus"];

type StatusBadgeProps = {
	status: Status;
};

const STATUS_ICONS = {
	READY: <Circle size={12} fill="green" />,
	NOT_READY: <Circle size={12} fill="red" />,
	PAUSED: <Pause size={12} />,
} as const satisfies Record<Status, React.ReactNode>;

const statusBadgeVariants = cva(
	"gap-2 px-2 text-foreground/80 font-mono font-light border border-foreground/10 shadow-none text-nowrap",
	{
		variants: {
			status: {
				READY:
					"bg-green-100 hover:bg-green-100 dark:bg-green-900 dark:hover:bg-green-900",
				NOT_READY:
					"bg-red-100 hover:bg-red-100 dark:bg-red-900 dark:hover:bg-red-900",
				PAUSED:
					"bg-gray-300 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-700",
			} satisfies Record<Status, string>,
		},
	},
);

export const StatusIcon = ({ status }: StatusBadgeProps) =>
	STATUS_ICONS[status];

export const StatusBadge = ({ status }: StatusBadgeProps) => {
	const statusText = status.split("_").map(capitalize).join(" ");
	return (
		<Badge className={statusBadgeVariants({ status })}>
			<StatusIcon status={status} />
			{statusText}
		</Badge>
	);
};
