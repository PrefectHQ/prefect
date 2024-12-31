import type { components } from "@/api/prefect";
import { cva } from "class-variance-authority";
import { Circle, Pause } from "lucide-react";
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
	"gap-2 px-2 text-black/80 font-mono font-light border border-black/10 shadow-none text-nowrap",
	{
		variants: {
			status: {
				READY: "bg-green-100 hover:bg-green-100",
				NOT_READY: "bg-red-100 hover:bg-red-100",
				PAUSED: "bg-gray-300 hover:bg-gray-300",
			} satisfies Record<Status, string>,
		},
	},
);

export const StatusBadge = ({ status }: StatusBadgeProps) => {
	const Icon = STATUS_ICONS[status];
	const statusText = status
		.split("_")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
		.join(" ");
	return (
		<Badge className={statusBadgeVariants({ status })}>
			{Icon}
			{statusText}
		</Badge>
	);
};
