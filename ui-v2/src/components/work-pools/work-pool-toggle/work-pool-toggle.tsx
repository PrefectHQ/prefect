import type { WorkPool } from "@/api/work-pools";
import { Switch } from "@/components/ui/switch";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";
import { useWorkPoolToggle } from "./hooks/use-work-pool-toggle";

type WorkPoolToggleProps = {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
};

export const WorkPoolToggle = ({
	workPool,
	onUpdate,
	className,
}: WorkPoolToggleProps) => {
	const { handleToggle, isLoading } = useWorkPoolToggle(workPool, onUpdate);
	const isPaused = workPool.status === "PAUSED";

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<div>
					<Switch
						checked={!isPaused}
						onCheckedChange={handleToggle}
						disabled={isLoading}
						aria-label={isPaused ? "Resume work pool" : "Pause work pool"}
						className={cn(className)}
					/>
				</div>
			</TooltipTrigger>
			<TooltipContent>
				<p>Pause or resume this work pool</p>
			</TooltipContent>
		</Tooltip>
	);
};
