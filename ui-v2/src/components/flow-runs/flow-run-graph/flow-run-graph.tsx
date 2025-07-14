import {
	emitter,
	type GraphItemSelection,
	type RunGraphConfig,
	type RunGraphNode,
	type RunGraphStateEvent,
	selectItem,
	setConfig,
	start,
	stop,
	updateViewportFromDateRange,
	type ViewportDateRange,
} from "@prefecthq/graphs";
import {
	type CSSProperties,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { fetchFlowRunEvents, fetchFlowRunGraph } from "./api";
import { stateTypeColors } from "./consts";
import { FlowRunGraphActions } from "./flow-run-graph-actions";

type FlowRunGraphProps = {
	flowRunId: string;
	viewport?: ViewportDateRange;
	onViewportChange?: (viewport: ViewportDateRange) => void;
	selected?: GraphItemSelection;
	onSelectedChange?: (selected: GraphItemSelection | undefined) => void;
	fullscreen?: boolean;
	onFullscreenChange?: (fullscreen: boolean) => void;
	className?: string;
	style?: CSSProperties;
};

export function FlowRunGraph({
	flowRunId,
	viewport,
	onViewportChange,
	selected,
	onSelectedChange,
	className,
	style,
	fullscreen: controlledFullscreen,
	onFullscreenChange,
}: FlowRunGraphProps) {
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

	const config = useMemo<RunGraphConfig>(
		() => ({
			runId: flowRunId,
			fetch: fetchFlowRunGraph,
			fetchEvents: fetchFlowRunEvents,
			styles: () => ({
				node: (node: RunGraphNode) => ({
					background: stateTypeColors[node.state_type],
				}),
				state: (event: RunGraphStateEvent) => ({
					background: stateTypeColors[event.type],
				}),
			}),
			theme: "light",
		}),
		[flowRunId],
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
		selectItem(selected ?? null);
	}, [selected]);

	useEffect(() => {
		void updateViewportFromDateRange(viewport);
	}, [viewport]);

	useEffect(() => {
		const offItemSelected = emitter.on("itemSelected", (nodeId) =>
			onSelectedChange?.(nodeId ?? undefined),
		);
		const offViewportDateRangeUpdated = emitter.on(
			"viewportDateRangeUpdated",
			(range) => onViewportChange?.(range),
		);

		return () => {
			offItemSelected();
			offViewportDateRangeUpdated();
		};
	}, [onSelectedChange, onViewportChange]);

	return (
		<div
			className={`${fullscreen ? "fixed h-screen w-screen z-20" : "relative h-[500px] w-full "} ${className ?? ""}`}
			style={style}
		>
			<div ref={stageRef} className="size-full [&>canvas]:size-full" />
			<div className="absolute bottom-0 right-0">
				<FlowRunGraphActions
					fullscreen={fullscreen}
					onFullscreenChange={updateFullscreen}
				/>
			</div>
		</div>
	);
}
