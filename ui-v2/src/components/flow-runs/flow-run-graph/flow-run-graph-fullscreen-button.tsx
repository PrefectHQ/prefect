import { useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons/icon";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { isEventTargetInput } from "./utilities";

type FlowRunGraphFullscreenButtonProps = {
	fullscreen: boolean;
	onFullscreenChange: (fullscreen: boolean) => void;
};

export function FlowRunGraphFullscreenButton({
	fullscreen,
	onFullscreenChange,
}: FlowRunGraphFullscreenButtonProps) {
	const toggleFullscreen = useCallback(() => {
		onFullscreenChange(!fullscreen);
	}, [fullscreen, onFullscreenChange]);

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

				if (event.key === "f") {
					toggleFullscreen();
					return;
				}

				if (event.key === "Escape") {
					toggleFullscreen();
					return;
				}
			},
			{ signal: controller.signal },
		);

		return () => controller.abort();
	}, [toggleFullscreen]);

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button variant="outline" size="icon" onClick={toggleFullscreen}>
					<Icon id="Expand" className="size-4" />
				</Button>
			</TooltipTrigger>
			<TooltipContent>Fullscreen (f)</TooltipContent>
		</Tooltip>
	);
}
