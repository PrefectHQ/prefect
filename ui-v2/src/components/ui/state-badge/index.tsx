import { cn } from "@/lib/utils";
import { Badge } from "../badge";
import type { components } from "@/api/prefect";

// These classes are needed to ensure Tailwind builds the state color classes
// bg-state-completed bg-state-pending bg-state-scheduled bg-state-running bg-state-failed bg-state-cancelled bg-state-crashed bg-state-paused bg-state-cancelling
// text-state-completed-foreground text-state-pending-foreground text-state-scheduled-foreground text-state-running-foreground text-state-failed-foreground text-state-cancelled-foreground text-state-crashed-foreground text-state-paused-foreground text-state-cancelling-foreground

export const StateBadge = ({
	state,
}: { state: components["schemas"]["State"] }) => {
	const className = cn(
		`bg-state-${state.type.toLowerCase()}`,
		`hover:bg-state-${state.type.toLowerCase()}/80`,
		`text-state-${state.type.toLowerCase()}-foreground`,
	);
	return <Badge className={className}>{state.name}</Badge>;
};
