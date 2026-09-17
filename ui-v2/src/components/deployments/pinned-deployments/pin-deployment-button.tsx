import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";
import { usePinnedDeployments } from "./use-pinned-deployments";

type PinDeploymentButtonProps = {
	deploymentId: string;
	className?: string;
};

export const PinDeploymentButton = ({
	deploymentId,
	className,
}: PinDeploymentButtonProps) => {
	const { isPinned, togglePin } = usePinnedDeployments();
	const pinned = isPinned(deploymentId);
	const label = pinned ? "Unpin deployment" : "Pin deployment";

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					aria-label={label}
					aria-pressed={pinned}
					className={cn(
						"size-8 p-0 text-muted-foreground",
						pinned && "text-foreground",
						className,
					)}
					onClick={(event) => {
						event.stopPropagation();
						togglePin(deploymentId);
					}}
				>
					<Icon id="Pin" className={cn("size-4", pinned && "fill-current")} />
				</Button>
			</TooltipTrigger>
			<TooltipContent>{label}</TooltipContent>
		</Tooltip>
	);
};
