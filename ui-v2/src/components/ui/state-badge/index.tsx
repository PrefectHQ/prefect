import { cn } from "@/lib/utils";
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
} as const;

export const StateBadge = ({
	state,
}: { state: components["schemas"]["State"] }) => {
	const className = cn(
		`bg-state-${state.type.toLowerCase()}-badge`,
		`hover:bg-state-${state.type.toLowerCase()}-badge`,
		`text-state-${state.type.toLowerCase()}-badge-foreground`,
	);
	const Icon = ICONS[state.type];
	return (
		<Badge className={className}>
			<div className="flex items-center gap-1">
				<Icon size={16} />

				{state.name}
			</div>
		</Badge>
	);
};

// These classes are needed to ensure Tailwind builds the state color classes
// These comments will ensure the classes are generated
// Background colors
// bg-state-completed-badge
// bg-state-pending-badge
// bg-state-scheduled-badge
// bg-state-running-badge
// bg-state-failed-badge
// bg-state-cancelled-badge
// bg-state-crashed-badge
// bg-state-paused-badge
// bg-state-cancelling-badge

// Foreground colors
// text-state-completed-badge-foreground
// text-state-pending-badge-foreground
// text-state-scheduled-badge-foreground
// text-state-running-badge-foreground
// text-state-failed-badge-foreground
// text-state-cancelled-badge-foreground
// text-state-crashed-badge-foreground
// text-state-paused-badge-foreground
// text-state-cancelling-badge-foreground
