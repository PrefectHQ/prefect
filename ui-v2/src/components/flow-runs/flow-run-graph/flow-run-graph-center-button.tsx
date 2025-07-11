import { centerViewport } from "@prefecthq/graphs";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons/icon";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { isEventTargetInput } from "./utilities";

const center = () => {
	void centerViewport({ animate: true });
};

export function FlowRunGraphCenterButton() {
	useEffect(() => {
		const controller = new AbortController();

		document.addEventListener(
			"keydown",
			(event: KeyboardEvent) => {
				if (
					isEventTargetInput(event.target) ||
					event.metaKey ||
					event.ctrlKey
				) {
					return;
				}

				if (event.key === "c") {
					center();
				}
			},
			{ signal: controller.signal },
		);

		return () => controller.abort();
	}, []);

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button variant="outline" size="icon" onClick={center}>
					<Icon id="Crosshair" className="size-4" />
				</Button>
			</TooltipTrigger>
			<TooltipContent>Recenter (c)</TooltipContent>
		</Tooltip>
	);
}
