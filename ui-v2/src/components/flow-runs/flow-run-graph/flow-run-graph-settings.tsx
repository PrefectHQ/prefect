import {
	DEFAULT_HORIZONTAL_SCALE_MULTIPLIER,
	type HorizontalMode,
	isHorizontalMode,
	isVerticalMode,
	layout,
	resetHorizontalScaleMultiplier,
	setDisabledArtifacts,
	setDisabledEdges,
	setDisabledEvents,
	setHorizontalMode,
	setHorizontalScaleMultiplier,
	setVerticalMode,
	type VerticalMode,
} from "@prefecthq/graphs";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Typography } from "@/components/ui/typography";

type LayoutOption = `${HorizontalMode}_${VerticalMode}`;

const layoutOptions: { label: string; value: LayoutOption }[] = [
	{
		label: "Temporal dependency",
		value: "temporal_nearest-parent",
	},
	{
		label: "Temporal sequence",
		value: "temporal_waterfall",
	},
	{
		label: "Dependency grid",
		value: "dependency_nearest-parent",
	},
	{
		label: "Sequential grid",
		value: "dependency_waterfall",
	},
	{
		label: "Comparative duration",
		value: "left-aligned_duration-sorted",
	},
];

const increaseScale = () => {
	const multiplier = DEFAULT_HORIZONTAL_SCALE_MULTIPLIER + 1;
	const scale = layout.horizontalScaleMultiplier * multiplier;
	setHorizontalScaleMultiplier(scale);
};

const decreaseScale = () => {
	const multiplier = Math.abs(DEFAULT_HORIZONTAL_SCALE_MULTIPLIER - 1);
	const scale = layout.horizontalScaleMultiplier * multiplier;
	setHorizontalScaleMultiplier(scale);
};

const resetScale = () => {
	resetHorizontalScaleMultiplier();
};

function isLayoutOption(value: string): value is LayoutOption {
	const [horizontal, vertical] = value.split("_");
	return isHorizontalMode(horizontal) && isVerticalMode(vertical);
}

export function FlowRunGraphSettings() {
	const [selectedLayoutOption, setSelectedLayoutOption] = useState(
		`${layout.horizontal}_${layout.vertical}`,
	);
	const [hideEdges, setHideEdges] = useState(layout.disableEdges);
	const [hideArtifacts, setHideArtifacts] = useState(layout.disableArtifacts);
	const [hideEvents, setHideEvents] = useState(layout.disableEvents);

	const handleLayoutChange = useCallback((value: string) => {
		if (!isLayoutOption(value)) {
			return;
		}

		const [horizontal, vertical] = value.split("_");

		if (!isHorizontalMode(horizontal) || !isVerticalMode(vertical)) {
			return;
		}

		setSelectedLayoutOption(value);
		setHorizontalMode(horizontal);
		setVerticalMode(vertical);
	}, []);

	const handleHideEdgesChange = useCallback((value: boolean) => {
		setHideEdges(value);
		setDisabledEdges(value);
	}, []);

	const handleHideArtifactsChange = useCallback((value: boolean) => {
		setHideArtifacts(value);
		setDisabledArtifacts(value);
	}, []);

	const handleHideEventsChange = useCallback((value: boolean) => {
		setHideEvents(value);
		setDisabledEvents(value);
	}, []);

	return (
		<div className="flex flex-col gap-2">
			<div className="flex flex-col gap-2">
				<Typography variant="bodyLarge">Layout</Typography>
				<div className="flex flex-col gap-2">
					{layoutOptions.map((option) => (
						<div key={option.value} className="flex items-center gap-2">
							<input
								type="radio"
								id={option.value}
								name="layout"
								value={option.value}
								checked={selectedLayoutOption === option.value}
								onChange={(e) => handleLayoutChange(e.target.value)}
							/>
							<Label htmlFor={option.value}>{option.label}</Label>
						</div>
					))}
				</div>
			</div>

			{(layout.isTemporal() || layout.isLeftAligned()) && (
				<div className="flex flex-col gap-2">
					<Typography variant="bodyLarge">Scaling</Typography>
					<div className="flex items-center gap-2">
						<Button
							variant="outline"
							size="sm"
							onClick={decreaseScale}
							title="Decrease scale (-)"
						>
							-
						</Button>
						<Button
							variant="outline"
							size="sm"
							onClick={increaseScale}
							title="Increase scale (+)"
						>
							+
						</Button>
						<Button variant="outline" size="sm" onClick={resetScale}>
							Reset
						</Button>
					</div>
				</div>
			)}

			<hr className="my-4" />

			<div className="flex flex-col gap-2">
				<div className="flex items-center gap-2">
					<Switch
						id="hideEdges"
						checked={hideEdges}
						onCheckedChange={handleHideEdgesChange}
					/>
					<Label htmlFor="hideEdges">Hide dependency arrows</Label>
				</div>

				<div className="flex items-center gap-2">
					<Switch
						id="hideArtifacts"
						checked={hideArtifacts}
						onCheckedChange={handleHideArtifactsChange}
					/>
					<Label htmlFor="hideArtifacts">Hide artifacts</Label>
				</div>

				<div className="flex items-center gap-2">
					<Switch
						id="hideEvents"
						checked={hideEvents}
						onCheckedChange={handleHideEventsChange}
					/>
					<Label htmlFor="hideEvents">Hide events</Label>
				</div>
			</div>
		</div>
	);
}
