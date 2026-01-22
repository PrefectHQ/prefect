import {
	emitter,
	type GraphItemSelection,
	isNodeSelection,
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
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import {
	type CSSProperties,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { buildCountFlowRunsQuery } from "@/api/flow-runs";
import { buildCountTaskRunsQuery } from "@/api/task-runs";
import { getStateColor } from "@/utils/state-colors";
import { fetchFlowRunEvents, fetchFlowRunGraph } from "./api";
import { stateTypeShades } from "./consts";
import { FlowRunGraphActions } from "./flow-run-graph-actions";
import { FlowRunGraphSelectionPanel } from "./flow-run-graph-selection-panel";

const TERMINAL_STATES = ["COMPLETED", "FAILED", "CANCELLED", "CRASHED"];

type FlowRunGraphProps = {
	flowRunId: string;
	stateType?: string;
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
	stateType,
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
	const { resolvedTheme } = useTheme();

	const fullscreen = controlledFullscreen ?? internalFullscreen;
	const isTerminal = stateType && TERMINAL_STATES.includes(stateType);

	const { data: taskRunCount } = useQuery(
		buildCountTaskRunsQuery({
			task_runs: {
				operator: "and_",
				flow_run_id: { operator: "and_", any_: [flowRunId], is_null_: false },
			},
		}),
	);

	const { data: subflowRunCount } = useQuery(
		buildCountFlowRunsQuery({
			flow_runs: {
				operator: "and_",
				parent_flow_run_id: {
					operator: "and_",
					any_: [flowRunId],
				},
			},
		}),
	);

	const hasNodes =
		taskRunCount === undefined ||
		subflowRunCount === undefined ||
		taskRunCount > 0 ||
		subflowRunCount > 0;

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
					background: getStateColor(
						node.state_type,
						stateTypeShades[node.state_type],
					),
				}),
				state: (event: RunGraphStateEvent) => ({
					background: getStateColor(event.type, stateTypeShades[event.type]),
				}),
			}),
			theme: resolvedTheme === "dark" ? "dark" : "light",
		}),
		[flowRunId, resolvedTheme],
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

	const heightClass = fullscreen
		? "fixed h-screen w-screen z-20"
		: hasNodes
			? "relative h-96 w-full"
			: "relative h-40 w-full";

	return (
		<div className={`${heightClass} ${className ?? ""}`} style={style}>
			<div ref={stageRef} className="size-full [&>canvas]:size-full" />
			{!hasNodes && (
				<div className="absolute inset-0 flex items-center justify-center bg-background/50">
					<p className="text-muted-foreground">
						{isTerminal
							? "This flow run did not generate any task or subflow runs"
							: "This flow run has not yet generated any task or subflow runs"}
					</p>
				</div>
			)}
			<div className="absolute bottom-0 right-0">
				<FlowRunGraphActions
					fullscreen={fullscreen}
					onFullscreenChange={updateFullscreen}
				/>
			</div>
			{selected && isNodeSelection(selected) && (
				<FlowRunGraphSelectionPanel
					selection={selected}
					onClose={() => onSelectedChange?.(undefined)}
				/>
			)}
		</div>
	);
}
