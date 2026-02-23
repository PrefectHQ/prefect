import { cva } from "class-variance-authority";
import type { components } from "@/api/prefect";

import { ICONS as COMPONENT_ICONS } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { capitalize, cn } from "@/utils";
import { Badge } from "../badge";

const STATE_ICONS = {
	COMPLETED: COMPONENT_ICONS.Check,
	FAILED: COMPONENT_ICONS.X,
	RUNNING: COMPONENT_ICONS.Play,
	CANCELLED: COMPONENT_ICONS.Ban,
	CANCELLING: COMPONENT_ICONS.Ban,
	CRASHED: COMPONENT_ICONS.ServerCrash,
	PAUSED: COMPONENT_ICONS.Pause,
	PENDING: COMPONENT_ICONS.Clock,
	SCHEDULED: COMPONENT_ICONS.Clock,
} as const satisfies Record<
	components["schemas"]["StateType"],
	React.ElementType
>;

const ICONS = STATE_ICONS;

const stateBadgeVariants = cva("gap-1", {
	variants: {
		state: {
			COMPLETED:
				"bg-state-completed-100 text-state-completed-600 hover:bg-state-completed-200",
			FAILED:
				"bg-state-failed-100 text-state-failed-700 hover:bg-state-failed-200",
			RUNNING:
				"bg-state-running-100 text-state-running-700 hover:bg-state-running-200",
			CANCELLED:
				"bg-state-cancelled-100 text-state-cancelled-600 hover:bg-state-cancelled-200",
			CANCELLING:
				"bg-state-cancelling-100 text-state-cancelling-600 hover:bg-state-cancelling-200",
			CRASHED:
				"bg-state-crashed-100 text-state-crashed-600 hover:bg-state-crashed-200",
			PAUSED:
				"bg-state-paused-100 text-state-paused-700 hover:bg-state-paused-200",
			PENDING:
				"bg-state-pending-100 text-state-pending-700 hover:bg-state-pending-200",
			SCHEDULED:
				"bg-state-scheduled-100 text-state-scheduled-700 hover:bg-state-scheduled-200",
		} satisfies Record<components["schemas"]["StateType"], string>,
	},
});

export type StateBadgeProps = {
	type: components["schemas"]["StateType"];
	name?: string | null;
	className?: string;
};

export const StateBadge = ({ type, name, className }: StateBadgeProps) => {
	const Icon = ICONS[type];
	return (
		<Badge
			className={cn(stateBadgeVariants({ state: type }), "px-2", className)}
		>
			<Icon size={16} />
			{name ?? capitalize(type)}
		</Badge>
	);
};

const STATE_ICON_COLORS = {
	COMPLETED: "text-state-completed-600",
	FAILED: "text-state-failed-700",
	RUNNING: "text-state-running-700",
	CANCELLED: "text-state-cancelled-600",
	CANCELLING: "text-state-cancelling-600",
	CRASHED: "text-state-crashed-600",
	PAUSED: "text-state-paused-700",
	PENDING: "text-state-pending-600",
	SCHEDULED: "text-state-scheduled-700",
} as const satisfies Record<components["schemas"]["StateType"], string>;

export type StateIconProps = {
	type: components["schemas"]["StateType"];
	name?: string | null;
	className?: string;
	size?: number;
};

export const StateIcon = ({
	type,
	name,
	className,
	size = 16,
}: StateIconProps) => {
	const Icon = STATE_ICONS[type];
	const tooltipText = name ?? capitalize(type);

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<span
					className={cn(
						"inline-flex items-center",
						STATE_ICON_COLORS[type],
						className,
					)}
				>
					<Icon size={size} />
				</span>
			</TooltipTrigger>
			<TooltipContent>{tooltipText}</TooltipContent>
		</Tooltip>
	);
};
