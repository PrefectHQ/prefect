import { toast } from "sonner";
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
	/**
	 * Inside a table row, hide the button until the row is hovered or the button
	 * is focused. Pinned deployments and devices without hover always show it.
	 */
	revealOnRowHover?: boolean;
	className?: string;
};

export const PinDeploymentButton = ({
	deploymentId,
	revealOnRowHover = false,
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
						"size-8 p-0",
						pinned
							? "text-foreground"
							: "text-foreground/60 hover:text-foreground",
						revealOnRowHover &&
							!pinned &&
							"opacity-0 transition-opacity focus-visible:opacity-100 [tr:hover_&]:opacity-100 [@media(hover:none)]:opacity-100",
						className,
					)}
					onClick={() => {
						if (!togglePin(deploymentId)) {
							toast.error("Could not save the pin in this browser");
						}
					}}
				>
					<Icon id="Pin" className={cn("size-4", pinned && "fill-current")} />
				</Button>
			</TooltipTrigger>
			<TooltipContent>{label}</TooltipContent>
		</Tooltip>
	);
};
