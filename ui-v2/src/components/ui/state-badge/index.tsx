import type { components } from "@/api/prefect";
import { cva } from "class-variance-authority";

import { ICONS as COMPONENT_ICONS } from "@/components/ui/icons";

import { Badge } from "../badge";

const ICONS = {
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

export const StateBadge = ({
	state,
}: { state: components["schemas"]["State"] }) => {
	const Icon = ICONS[state.type];
	return (
		<Badge className={stateBadgeVariants({ state: state.type })}>
			<Icon size={16} />
			{state.name}
		</Badge>
	);
};
