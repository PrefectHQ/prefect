import type { WorkPool } from "@/api/work-pools";
import { Switch } from "@/components/ui/switch";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useWorkPoolToggle } from "./hooks/use-work-pool-toggle";

interface WorkPoolToggleProps {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
}

export const WorkPoolToggle = ({
	workPool,
	onUpdate,
	className,
}: WorkPoolToggleProps) => {
	const { handleToggle, isLoading } = useWorkPoolToggle(workPool, onUpdate);
	const isPaused = workPool.status === "PAUSED";

	// Only show if user has update permissions
	// For now, we'll show it always since permissions aren't fully implemented
	// TODO: Check workPool.can?.update when permissions are available

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Switch
					checked={!isPaused}
					onCheckedChange={handleToggle}
					disabled={isLoading}
					aria-label={isPaused ? "Resume work pool" : "Pause work pool"}
					className={cn(className)}
				/>
			</TooltipTrigger>
			<TooltipContent>
				<p>Pause or resume this work pool</p>
			</TooltipContent>
		</Tooltip>
	);
};
