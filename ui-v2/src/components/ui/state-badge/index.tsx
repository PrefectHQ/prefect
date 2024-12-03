import { Badge } from "../badge";
import type { components } from "@/api/prefect";
import {
	ClockIcon,
	PauseIcon,
	XIcon,
	CheckIcon,
	ServerCrashIcon,
	BanIcon,
	PlayIcon,
} from "lucide-react";

const ICONS = {
	COMPLETED: CheckIcon,
	FAILED: XIcon,
	RUNNING: PlayIcon,
	CANCELLED: BanIcon,
	CANCELLING: BanIcon,
	CRASHED: ServerCrashIcon,
	PAUSED: PauseIcon,
	PENDING: ClockIcon,
	SCHEDULED: ClockIcon,
} as const satisfies Record<
	components["schemas"]["StateType"],
	React.ElementType
>;

const CLASSES = {
	COMPLETED: "bg-green-50 text-green-600 hover:bg-green-50",
	FAILED: "bg-red-50 text-red-600 hover:bg-red-50",
	RUNNING: "bg-blue-100 text-blue-700 hover:bg-blue-100",
	CANCELLED: "bg-gray-300 text-gray-800 hover:bg-gray-300",
	CANCELLING: "bg-gray-300 text-gray-800 hover:bg-gray-300",
	CRASHED: "bg-orange-50 text-orange-600 hover:bg-orange-50",
	PAUSED: "bg-gray-300 text-gray-800 hover:bg-gray-300",
	PENDING: "bg-gray-300 text-gray-800 hover:bg-gray-300",
	SCHEDULED: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
} as const satisfies Record<components["schemas"]["StateType"], string>;

export const StateBadge = ({
	state,
}: { state: components["schemas"]["State"] }) => {
	const Icon = ICONS[state.type];
	return (
		<Badge className={CLASSES[state.type]}>
			<div className="flex items-center gap-1">
				<Icon size={16} />

				{state.name}
			</div>
		</Badge>
	);
};
