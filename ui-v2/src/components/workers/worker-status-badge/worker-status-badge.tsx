import { cva } from "class-variance-authority";
import { AlertCircle, CheckCircle } from "lucide-react";
import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";

type WorkerStatus = components["schemas"]["WorkerStatus"];

interface WorkerStatusBadgeProps {
	status: WorkerStatus;
	className?: string;
}

const statusConfig = {
	ONLINE: {
		icon: CheckCircle,
		label: "Online",
	},
	OFFLINE: {
		icon: AlertCircle,
		label: "Offline",
	},
} as const satisfies Record<
	WorkerStatus,
	{ icon: React.ComponentType<React.SVGProps<SVGSVGElement>>; label: string }
>;

const workerStatusBadgeVariants = cva(
	"gap-2 px-2 text-black/80 font-mono font-light border border-black/10 shadow-none text-nowrap",
	{
		variants: {
			status: {
				ONLINE: "bg-green-100 hover:bg-green-100 text-green-800",
				OFFLINE: "bg-gray-100 hover:bg-gray-100 text-gray-600",
			} satisfies Record<WorkerStatus, string>,
		},
	},
);

export const WorkerStatusBadge = ({
	status,
	className,
}: WorkerStatusBadgeProps) => {
	const config = statusConfig[status];
	const Icon = config.icon;

	return (
		<Badge className={workerStatusBadgeVariants({ status, className })}>
			<Icon size={12} />
			{config.label}
		</Badge>
	);
};
