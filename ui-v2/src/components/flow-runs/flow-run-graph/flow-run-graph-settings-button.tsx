import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons/icon";
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

export function FlowRunGraphSettingsButton() {
	return (
		<Popover>
			<PopoverTrigger>
				<Tooltip>
					<TooltipTrigger asChild>
						<Button variant="outline" size="icon">
							<Icon id="Cog" className="size-4" />
						</Button>
					</TooltipTrigger>
					<TooltipContent>Settings</TooltipContent>
				</Tooltip>
			</PopoverTrigger>
			<PopoverContent>
				<FlowRunGraphSettings />
			</PopoverContent>
		</Popover>
	);
}
