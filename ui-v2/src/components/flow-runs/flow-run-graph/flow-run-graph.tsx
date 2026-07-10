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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	emitter,
	type GraphItemSelection,
	isArtifactsSelection,
	isEventSelection,
	isEventsSelection,
	isNodeSelection,
	isStateSelection,
	type RunGraphConfig,
	type RunGraphNode,
	type RunGraphStateEvent,
	refreshRunData,
	selectItem,
	setConfig,
	start,
	stop,
	updateViewportFromDateRange,
	type ViewportDateRange,
} from "@/graphs";
import { getStateColor } from "@/utils/state-colors";
import { fetchFlowRunEvents, fetchFlowRunGraph } from "./api";
import { getStateTypeShade } from "./consts";
import { FlowRunGraphActions } from "./flow-run-graph-actions";
import { FlowRunGraphArtifactDrawer } from "./flow-run-graph-artifact-drawer";
import { FlowRunGraphArtifactsPopover } from "./flow-run-graph-artifacts-popover";
import { FlowRunGraphEventPopover } from "./flow-run-graph-event-popover";
import { FlowRunGraphEventsPopover } from "./flow-run-graph-events-popover";
import { FlowRunGraphSelectionPanel } from "./flow-run-graph-selection-panel";
import { FlowRunGraphStatePopover } from "./flow-run-graph-state-popover";
import {
	filterRunGraphDataByFlowRunAttempt,
	getFlowRunAttemptRunCounts,
} from "./utilities";

const TERMINAL_STATES = ["COMPLETED", "FAILED", "CANCELLED", "CRASHED"];
const ALL_ATTEMPTS = "all";

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
	selected: controlledSelected,
	onSelectedChange,
	className,
	style,
	fullscreen: controlledFullscreen,
	onFullscreenChange,
}: FlowRunGraphProps) {
	const stageRef = useRef<HTMLDivElement>(null);
	const [internalFullscreen, setInternalFullscreen] = useState(false);
	const [internalSelected, setInternalSelected] = useState<
		GraphItemSelection | undefined
	>(undefined);
	const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(
		null,
	);
	const [attemptRunCounts, setAttemptRunCounts] = useState<number[]>([]);
	const [selectedAttemptRunCount, setSelectedAttemptRunCount] = useState<
		number | typeof ALL_ATTEMPTS | null
	>(null);
	const selectedAttemptRunCountRef = useRef<
		number | typeof ALL_ATTEMPTS | null
	>(null);
	const { resolvedTheme } = useTheme();

	const fullscreen = controlledFullscreen ?? internalFullscreen;
	const selected = controlledSelected ?? internalSelected;
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

	const fetchGraph = useCallback(async (id: string) => {
		const data = await fetchFlowRunGraph(id);
		const runCounts = getFlowRunAttemptRunCounts(data);
		const selectedAttemptRunCount = selectedAttemptRunCountRef.current;
		const fallbackAttempt =
			runCounts.length > 1 ? runCounts[runCounts.length - 1] : ALL_ATTEMPTS;
		const shouldUseFallback =
			selectedAttemptRunCount === null ||
			(selectedAttemptRunCount !== ALL_ATTEMPTS &&
				!runCounts.includes(selectedAttemptRunCount));
		const nextSelectedAttempt = shouldUseFallback
			? fallbackAttempt
			: selectedAttemptRunCount;

		setAttemptRunCounts(runCounts);
		if (
			runCounts.length > 1 &&
			nextSelectedAttempt !== selectedAttemptRunCount
		) {
			selectedAttemptRunCountRef.current = nextSelectedAttempt;
			setSelectedAttemptRunCount(nextSelectedAttempt);
		} else if (runCounts.length <= 1 && selectedAttemptRunCount !== null) {
			selectedAttemptRunCountRef.current = null;
			setSelectedAttemptRunCount(null);
		}

		return filterRunGraphDataByFlowRunAttempt(data, nextSelectedAttempt);
	}, []);

	const config = useMemo<RunGraphConfig>(
		() => ({
			runId: flowRunId,
			fetch: fetchGraph,
			fetchEvents: fetchFlowRunEvents,
			styles: (theme) => ({
				node: (node: RunGraphNode) => ({
					background: getStateColor(
						node.state_type,
						getStateTypeShade(node.state_type, theme),
					),
				}),
				state: (event: RunGraphStateEvent) => ({
					background: getStateColor(
						event.type,
						getStateTypeShade(event.type, theme),
					),
				}),
			}),
			theme: resolvedTheme === "dark" ? "dark" : "light",
		}),
		[fetchGraph, flowRunId, resolvedTheme],
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
		const offItemSelected = emitter.on("itemSelected", (nodeId) => {
			const selection = nodeId ?? undefined;
			setInternalSelected(selection);
			onSelectedChange?.(selection);
		});
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
		? "fixed inset-0 z-50 bg-background"
		: hasNodes
			? "relative h-96 w-full"
			: "relative h-40 w-full";

	return (
		<div className={`${heightClass} ${className ?? ""}`} style={style}>
			<div ref={stageRef} className="size-full [&>canvas]:size-full" />
			{attemptRunCounts.length > 1 && selectedAttemptRunCount !== null && (
				<div className="absolute left-2 top-2">
					<Select
						value={selectedAttemptRunCount.toString()}
						onValueChange={(value) => {
							const nextSelectedAttempt =
								value === ALL_ATTEMPTS ? ALL_ATTEMPTS : Number(value);

							selectedAttemptRunCountRef.current = nextSelectedAttempt;
							setSelectedAttemptRunCount(nextSelectedAttempt);
							setInternalSelected(undefined);
							onSelectedChange?.(undefined);
							refreshRunData();
						}}
					>
						<SelectTrigger aria-label="Flow run attempt" className="bg-card">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{attemptRunCounts.map((runCount) => (
								<SelectItem key={runCount} value={runCount.toString()}>
									Run {runCount}
								</SelectItem>
							))}
							<SelectItem value={ALL_ATTEMPTS}>All runs</SelectItem>
						</SelectContent>
					</Select>
				</div>
			)}
			{!hasNodes && (
				<div className="absolute inset-0 flex items-center justify-center bg-background/50">
					<p className="text-muted-foreground">
						{isTerminal
							? "This flow run did not generate any task or subflow runs"
							: "This flow run has not yet generated any task or subflow runs"}
					</p>
				</div>
			)}
			<div className="absolute bottom-2 right-2">
				<FlowRunGraphActions
					fullscreen={fullscreen}
					onFullscreenChange={updateFullscreen}
				/>
			</div>
			{selected && isNodeSelection(selected) && (
				<FlowRunGraphSelectionPanel
					selection={selected}
					onClose={() => {
						setInternalSelected(undefined);
						onSelectedChange?.(undefined);
					}}
				/>
			)}
			{selected && isStateSelection(selected) && (
				<FlowRunGraphStatePopover
					selection={selected}
					onClose={() => {
						setInternalSelected(undefined);
						onSelectedChange?.(undefined);
					}}
				/>
			)}
			{selected && isEventSelection(selected) && (
				<FlowRunGraphEventPopover
					selection={selected}
					onClose={() => {
						setInternalSelected(undefined);
						onSelectedChange?.(undefined);
					}}
				/>
			)}
			{selected && isEventsSelection(selected) && (
				<FlowRunGraphEventsPopover
					selection={selected}
					onClose={() => {
						setInternalSelected(undefined);
						onSelectedChange?.(undefined);
					}}
				/>
			)}
			{selected && isArtifactsSelection(selected) && (
				<FlowRunGraphArtifactsPopover
					selection={selected}
					onClose={() => {
						setInternalSelected(undefined);
						onSelectedChange?.(undefined);
					}}
					onViewArtifact={(artifactId) => {
						setSelectedArtifactId(artifactId);
						setInternalSelected(undefined);
						onSelectedChange?.(undefined);
					}}
				/>
			)}
			<FlowRunGraphArtifactDrawer
				artifactId={selectedArtifactId}
				onClose={() => setSelectedArtifactId(null)}
			/>
		</div>
	);
}
