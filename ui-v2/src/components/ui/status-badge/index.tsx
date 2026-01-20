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
					"bg-state-completed-100 hover:bg-state-completed-100 dark:bg-state-completed-900 dark:hover:bg-state-completed-900",
				NOT_READY:
					"bg-state-failed-100 hover:bg-state-failed-100 dark:bg-state-failed-900 dark:hover:bg-state-failed-900",
				PAUSED:
					"bg-state-pending-200 hover:bg-state-pending-200 dark:bg-state-pending-800 dark:hover:bg-state-pending-800",
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
