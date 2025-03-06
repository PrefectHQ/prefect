import { FlowRunGraphCenterButton } from "./flow-run-graph-center-button";
import { FlowRunGraphFullscreenButton } from "./flow-run-graph-fullscreen-button";
import { FlowRunGraphSettingsButton } from "./flow-run-graph-settings-button";

type FlowRunGraphActionsProps = {
	fullscreen: boolean;
	onFullscreenChange: (fullscreen: boolean) => void;
};

export function FlowRunGraphActions({
	fullscreen,
	onFullscreenChange,
}: FlowRunGraphActionsProps) {
	return (
		<div className="flex gap-2">
			<FlowRunGraphCenterButton />
			<FlowRunGraphFullscreenButton
				fullscreen={fullscreen}
				onFullscreenChange={onFullscreenChange}
			/>
			<FlowRunGraphSettingsButton />
		</div>
	);
}
