import {
	GraphItemSelection,
	RunGraphConfig,
	ViewportDateRange,
	centerViewport,
	emitter,
	selectItem,
	setConfig,
	start,
	stop,
	updateViewportFromDateRange,
} from "@prefecthq/graphs";
import { CSSProperties, useCallback, useEffect, useRef, useState } from "react";

type RunGraphProps = {
	config: RunGraphConfig;
	viewport?: ViewportDateRange;
	onViewportChange?: (viewport: ViewportDateRange) => void;
	selected?: GraphItemSelection;
	onSelectedChange?: (selected: GraphItemSelection | undefined) => void;
	fullscreen?: boolean;
	onFullscreenChange?: (fullscreen: boolean) => void;
	className?: string;
	style?: CSSProperties;
};

export function RunGraph({
	viewport,
	onViewportChange,
	selected,
	onSelectedChange,
	config,
	className,
	style,
	fullscreen: controlledFullscreen,
	onFullscreenChange,
}: RunGraphProps) {
	const stageRef = useRef<HTMLDivElement>(null);
	const [internalFullscreen, setInternalFullscreen] = useState(false);

	const fullscreen = controlledFullscreen ?? internalFullscreen;

	const updateFullscreen = useCallback(
		(value: boolean) => {
			setInternalFullscreen(value);
			onFullscreenChange?.(value);
		},
		[onFullscreenChange],
	);

	useEffect(() => {
		setConfig(config);
	}, [config]);

	useEffect(() => {
		if (!stageRef.current) {
			throw new Error("Stage does not exist");
		}

		start({
			stage: stageRef.current,
			config,
		});

		return () => {
			stop();
		};
	}, [config]);

	useEffect(() => {
		if (selected !== undefined) {
			selectItem(selected);
		}
	}, [selected]);

	useEffect(() => {
		if (viewport) {
			void updateViewportFromDateRange(viewport);
		}
	}, [viewport]);

	useEffect(() => {
		const handleItemSelected = (nodeId: GraphItemSelection | null) => {
			onSelectedChange?.(nodeId ?? undefined);
		};

		const handleViewportUpdate = (range: ViewportDateRange) => {
			onViewportChange?.(range);
		};

		emitter.on("itemSelected", handleItemSelected);
		emitter.on("viewportDateRangeUpdated", handleViewportUpdate);

		return () => {
			emitter.off("itemSelected", handleItemSelected);
			emitter.off("viewportDateRangeUpdated", handleViewportUpdate);
		};
	}, [onSelectedChange, onViewportChange]);

	const toggleFullscreen = useCallback(() => {
		updateFullscreen(!fullscreen);
	}, [fullscreen, updateFullscreen]);

	useEffect(() => {
		const handleKeyDown = (event: KeyboardEvent) => {
			if (isEventTargetInput(event.target) || event.metaKey || event.ctrlKey) {
				return;
			}

			switch (event.key) {
				case "c":
					center();
					break;
				case "f":
					toggleFullscreen();
					break;
				case "Escape":
					if (fullscreen) {
						toggleFullscreen();
					}
					break;
			}
		};

		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [fullscreen, toggleFullscreen]);

	const center = () => {
		void centerViewport({ animate: true });
	};

	const isEventTargetInput = (target: EventTarget | null): boolean => {
		if (!target || !(target instanceof HTMLElement)) {
			return false;
		}
		return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
	};

	return (
		<div
			className={`relative h-[500px] w-full ${fullscreen ? "run-graph--fullscreen" : ""} ${className ?? ""}`}
			style={style}
		>
			<div ref={stageRef} className="size-full [&>canvas]:size-full" />
			<div className="run-graph__actions">
				<button
					title="Recenter graph (c)"
					onClick={center}
					className="p-button p-button--flat"
				>
					Recenter
				</button>
				<button
					title="Toggle fullscreen (f)"
					onClick={toggleFullscreen}
					className="p-button p-button--flat"
				>
					Fullscreen
				</button>
			</div>
		</div>
	);
}
