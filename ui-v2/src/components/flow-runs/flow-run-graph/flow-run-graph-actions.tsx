import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { FlowRunGraphSettings } from "./flow-run-graph-settings";

type FlowRunGraphActionsProps = {
	center: () => void;
	toggleFullscreen: () => void;
};

export function FlowRunGraphActions({
	center,
	toggleFullscreen,
}: FlowRunGraphActionsProps) {
	return (
		<div className="flex gap-2">
			{/* <Tooltip> */}
			{/* <TooltipTrigger asChild> */}
			<Button variant="outline" size="icon" onClick={center}>
				<Icon id="Shrink" className="size-4" />
			</Button>
			{/* </TooltipTrigger> */}
			{/* <TooltipContent>Recenter (c)</TooltipContent> */}
			{/* </Tooltip> */}
			{/* <Tooltip> */}
			{/* <TooltipTrigger asChild> */}
			<Button variant="outline" size="icon" onClick={toggleFullscreen}>
				<Icon id="Expand" className="size-4" />
			</Button>
			{/* </TooltipTrigger> */}
			{/* <TooltipContent>Fullscreen (f)</TooltipContent> */}
			{/* </Tooltip> */}
			<Popover>
				<PopoverTrigger asChild>
					<Button variant="outline" size="icon">
						<Icon id="Cog" className="size-4" />
					</Button>
				</PopoverTrigger>
				<PopoverContent>
					<FlowRunGraphSettings />
				</PopoverContent>
			</Popover>
		</div>
	);
}
