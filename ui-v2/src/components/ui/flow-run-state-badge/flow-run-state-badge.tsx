import { Badge } from "@/components/ui/badge";
import { ICONS as COMPONENT_ICONS } from "@/components/ui/icons";
import { cva } from "class-variance-authority";
import type { FlowRunStates } from "./flow-run-states";

const ICONS = {
	Scheduled: COMPONENT_ICONS.Clock,
	Late: COMPONENT_ICONS.Clock,
	Resuming: COMPONENT_ICONS.Clock,
	AwaitingRetry: COMPONENT_ICONS.Clock,
	AwaitingConcurrencySlot: COMPONENT_ICONS.Clock,
	Pending: COMPONENT_ICONS.Clock,
	Paused: COMPONENT_ICONS.Pause,
	Suspended: COMPONENT_ICONS.Pause,
	Running: COMPONENT_ICONS.Play,
	Retrying: COMPONENT_ICONS.Play,
	Completed: COMPONENT_ICONS.Check,
	Cached: COMPONENT_ICONS.Check,
	Cancelled: COMPONENT_ICONS.Ban,
	Cancelling: COMPONENT_ICONS.Ban,
	Crashed: COMPONENT_ICONS.ServerCrash,
	Failed: COMPONENT_ICONS.X,
	TimedOut: COMPONENT_ICONS.X,
} as const satisfies Record<FlowRunStates, React.ElementType>;

const flowRunStateVariants = cva("gap-1", {
	variants: {
		state: {
			Scheduled: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
			Late: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
			Resuming: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
			AwaitingRetry: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
			AwaitingConcurrencySlot:
				"bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
			Pending: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			Paused: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			Suspended: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			Running: "bg-blue-100 text-blue-700 hover:bg-blue-100",
			Retrying: "bg-blue-100 text-blue-700 hover:bg-blue-100",
			Completed: "bg-green-50 text-green-600 hover:bg-green-50",
			Cancelled: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			Cancelling: "bg-gray-300 text-gray-800 hover:bg-gray-300",
			Cached: "bg-green-50 text-green-600 hover:bg-green-50",
			Crashed: "bg-orange-50 text-orange-600 hover:bg-orange-50",
			Failed: "bg-red-50 text-red-600 hover:bg-red-50",
			TimedOut: "bg-red-50 text-red-600 hover:bg-red-50",
		} satisfies Record<FlowRunStates, string>,
	},
});

type FlowRunStateProps = {
	state: FlowRunStates;
};
export const FlowRunStateBadge = ({ state }: FlowRunStateProps) => {
	const Icon = ICONS[state];
	return (
		<Badge className={flowRunStateVariants({ state })}>
			<Icon size={16} />
			{state}
		</Badge>
	);
};
