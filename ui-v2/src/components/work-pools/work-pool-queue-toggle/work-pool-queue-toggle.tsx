import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Switch } from "@/components/ui/switch";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useWorkPoolQueueToggle } from "./hooks/use-work-pool-queue-toggle";

interface WorkPoolQueueToggleProps {
	queue: WorkPoolQueue;
	onUpdate?: () => void;
	disabled?: boolean;
	className?: string;
}

export const WorkPoolQueueToggle = ({
	queue,
	onUpdate,
	disabled = false,
	className,
}: WorkPoolQueueToggleProps) => {
	const { handleToggle, isLoading } = useWorkPoolQueueToggle(queue, onUpdate);
	const isPaused = queue.status === "PAUSED";
	const isDefaultQueue = queue.name === "default";

	// Default queue cannot be paused
	const isDisabled = disabled || isLoading || isDefaultQueue;

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<div>
						<Switch
							checked={!isPaused}
							onCheckedChange={handleToggle}
							disabled={isDisabled}
							aria-label={
								isPaused ? "Resume work pool queue" : "Pause work pool queue"
							}
							className={cn(className)}
						/>
					</div>
				</TooltipTrigger>
				<TooltipContent>
					<p>
						{isDefaultQueue
							? "Default queue cannot be paused"
							: "Pause or resume this work pool queue"}
					</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
