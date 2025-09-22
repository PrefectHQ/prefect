import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Switch } from "@/components/ui/switch";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";
import { useWorkPoolQueueToggle } from "./hooks/use-work-pool-queue-toggle";

type WorkPoolQueueToggleProps = {
	queue: WorkPoolQueue;
	onUpdate?: () => void;
	disabled?: boolean;
	className?: string;
};

export const WorkPoolQueueToggle = ({
	queue,
	onUpdate,
	disabled = false,
	className,
}: WorkPoolQueueToggleProps) => {
	const { handleToggle, isLoading } = useWorkPoolQueueToggle(queue, onUpdate);
	const isPaused = queue.status === "PAUSED";

	const isDisabled = disabled || isLoading;

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
					<p>Pause or resume this work pool queue</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
