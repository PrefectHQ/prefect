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
			COMPLETED: "bg-green-50 text-green-600 hover:bg-green-50",
			FAILED: "bg-red-50 text-red-600 hover:bg-red-50",
			RUNNING: "bg-blue-100 text-blue-700 hover:bg-blue-100",
			CANCELLED: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			CANCELLING: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			CRASHED: "bg-orange-50 text-orange-600 hover:bg-orange-50",
			PAUSED: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			PENDING: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			SCHEDULED: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
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
	COMPLETED: "text-green-600",
	FAILED: "text-red-600",
	RUNNING: "text-blue-700",
	CANCELLED: "text-gray-600",
	CANCELLING: "text-gray-600",
	CRASHED: "text-orange-600",
	PAUSED: "text-gray-600",
	PENDING: "text-gray-500",
	SCHEDULED: "text-yellow-600",
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
