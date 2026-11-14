import { useNavigate, useRouter } from "@tanstack/react-router";
import { scaleLog, scaleTime } from "d3";
import {
	type KeyboardEvent,
	type PointerEvent,
	type RefObject,
	useCallback,
	useEffect,
	useLayoutEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import type { SimpleFlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { Skeleton } from "@/components/ui/skeleton";
import { getAllStateColors } from "@/utils/state-colors";
import {
	drawScatter,
	type ScatterGeometry,
	type ScatterPalette,
} from "./draw-scatter";
import { ScatterPlotLegend } from "./scatter-plot-legend";
import { ScatterPlotReadout } from "./scatter-plot-readout";
import {
	countRunsByState,
	createXAxisTickFormatter,
	durationAxis,
	findNearestPoint,
	loadedSince,
	type PlotPoint,
	resolveTimeWindow,
	STATE_DRAW_ORDER,
	summarizeRuns,
	thinTicks,
} from "./scatter-plot-utils";

type StateType = components["schemas"]["StateType"];
type HistoryResponse = components["schemas"]["HistoryResponse"];

type FlowRunsScatterPlotProps = {
	/** Undefined while the history is loading. */
	history: SimpleFlowRun[] | undefined;
	startDate?: Date;
	endDate?: Date;
	/** Runs matching the page's filters, to tell when the history was cut short. */
	totalCount?: number;
	/** Called with the span a person drags across; omit to disable zooming. */
	onRangeChange?: (range: { startDate: Date; endDate: Date }) => void;
	/** The page's state type filter, which the legend chips set. */
	selectedStateTypes?: ReadonlySet<StateType>;
	onSelectedStateTypesChange?: (types: Set<StateType>) => void;
	/** Run counts per state for the window without the state type filter, so
	 * the legend keeps a chip for every state while one is selected. */
	stateHistory?: readonly HistoryResponse[];
};

const MARGIN = { top: 10, right: 12, bottom: 22, left: 46 };
const LANE_HEIGHT = 12;
const LANE_GAP = 12;
/** Keeps points at the window's edges fully inside the plot. */
const EDGE_PADDING = 6;
/** Hatched strip marking that older runs exist but were not loaded. */
const UNLOADED_STRIP = 12;
const BRUSH_THRESHOLD = 8;
const hitRadius = (pointerType: string) => (pointerType === "mouse" ? 12 : 24);

const drawRank = new Map<StateType, number>(
	STATE_DRAW_ORDER.map((state, index) => [state, index]),
);

export const FlowRunsScatterPlot = ({
	history,
	startDate,
	endDate,
	totalCount,
	onRangeChange,
	selectedStateTypes,
	onSelectedStateTypesChange,
	stateHistory,
}: FlowRunsScatterPlotProps) => {
	const containerRef = useRef<HTMLDivElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const size = useElementSize(containerRef);
	const palette = useScatterPalette();
	const navigate = useNavigate();
	const router = useRouter();

	const [hoverId, setHoverId] = useState<string>();
	const [pinnedId, setPinnedId] = useState<string>();
	const [brush, setBrush] = useState<{ from: number; to: number }>();
	const gesture = useRef<{
		pointerId: number;
		x: number;
		y: number;
		brushing: boolean;
	} | null>(null);

	const allRuns = useMemo(() => history ?? [], [history]);
	// A count below the runs already loaded is one that hasn't arrived yet.
	const knownTotal =
		totalCount !== undefined && totalCount >= allRuns.length
			? totalCount
			: undefined;
	const since = useMemo(
		() => loadedSince(allRuns, knownTotal),
		[allRuns, knownTotal],
	);
	const timeWindow = useMemo(() => {
		const requested = resolveTimeWindow({
			runs: allRuns,
			startDate,
			endDate,
			now: Date.now(),
		});
		// Spend the width on the runs that loaded, not on a span known to be
		// incomplete; the readout says how much was left out.
		if (since === undefined || since <= requested.start) return requested;
		return {
			...requested,
			start: since - (requested.end - since) * 0.02,
		};
	}, [allRuns, startDate, endDate, since]);
	const runs = useMemo(
		() =>
			allRuns.filter((run) => {
				const time = Date.parse(run.timestamp);
				return time >= timeWindow.start && time <= timeWindow.end;
			}),
		[allRuns, timeWindow],
	);
	const summary = useMemo(() => summarizeRuns(runs), [runs]);
	const legendCounts = useMemo(
		() => (stateHistory ? countRunsByState(stateHistory) : summary.byState),
		[stateHistory, summary],
	);
	const axis = useMemo(
		() => durationAxis(runs.map((run) => run.duration)),
		[runs],
	);

	const layout = useMemo(() => {
		if (size.width === 0 || size.height === 0) return undefined;
		const axisY = size.height - MARGIN.bottom;
		const geometry: ScatterGeometry = {
			width: size.width,
			height: size.height,
			left: MARGIN.left,
			right: size.width - MARGIN.right,
			top: MARGIN.top,
			logBottom: axisY - LANE_HEIGHT - LANE_GAP,
			laneY: axisY - LANE_HEIGHT / 2,
			axisY,
		};
		const unloadedUntilX =
			since === undefined ? undefined : geometry.left + UNLOADED_STRIP;
		const x = scaleTime()
			.domain([timeWindow.start, timeWindow.end])
			.range([
				(unloadedUntilX ?? geometry.left) + EDGE_PADDING,
				geometry.right - EDGE_PADDING,
			])
			.clamp(true);
		const y = scaleLog()
			.domain(axis.domain)
			.range([geometry.logBottom, geometry.top]);

		const points: PlotPoint[] = [...runs]
			.sort(
				(a, b) =>
					(drawRank.get(a.state_type) ?? 0) - (drawRank.get(b.state_type) ?? 0),
			)
			.map((run) => ({
				run,
				x: x(new Date(run.timestamp)),
				y: run.duration > 0 ? y(run.duration) : geometry.laneY,
			}));

		const plotWidth = geometry.right - geometry.left;
		const plotArea = plotWidth * (geometry.axisY - geometry.top);
		const radius = Math.min(
			5,
			Math.max(2.5, Math.sqrt(plotArea / Math.max(points.length, 1)) * 0.22),
		);

		const formatTime = createXAxisTickFormatter();
		const timeTicks = x
			.ticks(Math.max(2, Math.floor(plotWidth / 110)))
			.map((date) => ({ x: x(date), label: formatTime(date.getTime()) }));
		const durationTicks = thinTicks(
			axis.ticks,
			geometry.logBottom - geometry.top,
			22,
		).map((tick) => ({ y: y(tick.seconds), label: tick.label }));

		const now = Date.now();
		const span = timeWindow.end - timeWindow.start;
		const nowX =
			now > timeWindow.start && timeWindow.end - now > span / 100
				? x(new Date(now))
				: undefined;

		return {
			geometry,
			x,
			points,
			radius,
			timeTicks,
			durationTicks,
			nowX,
			unloadedUntilX,
		};
	}, [size, timeWindow, axis, runs, since]);

	const timeOrder = useMemo(
		() => [...(layout?.points ?? [])].sort((a, b) => a.x - b.x),
		[layout],
	);

	const activeId = hoverId ?? pinnedId;
	const active = useMemo(
		() =>
			activeId === undefined
				? undefined
				: timeOrder.find((point) => point.run.id === activeId),
		[activeId, timeOrder],
	);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas || !layout) return;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		const ratio = globalThis.devicePixelRatio || 1;
		const width = Math.round(layout.geometry.width * ratio);
		const height = Math.round(layout.geometry.height * ratio);
		if (canvas.width !== width) canvas.width = width;
		if (canvas.height !== height) canvas.height = height;
		ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
		drawScatter(ctx, { ...layout, palette });
	}, [layout, palette]);

	const openRun = useCallback(
		(id: string, newTab: boolean) => {
			if (newTab) {
				const { href } = router.buildLocation({
					to: "/runs/flow-run/$id",
					params: { id },
				});
				globalThis.open(href, "_blank", "noopener");
				return;
			}
			void navigate({ to: "/runs/flow-run/$id", params: { id } });
		},
		[navigate, router],
	);

	const localPoint = (event: PointerEvent<HTMLCanvasElement>) => {
		const bounds = event.currentTarget.getBoundingClientRect();
		return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
	};

	const onPointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
		if (event.pointerType === "mouse" && event.button !== 0) return;
		gesture.current = {
			pointerId: event.pointerId,
			...localPoint(event),
			brushing: false,
		};
	};

	const onPointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
		if (!layout) return;
		const point = localPoint(event);
		const current = gesture.current;
		if (current?.pointerId === event.pointerId) {
			const dx = point.x - current.x;
			const dy = point.y - current.y;
			if (
				!current.brushing &&
				onRangeChange &&
				Math.abs(dx) > BRUSH_THRESHOLD &&
				Math.abs(dx) > Math.abs(dy)
			) {
				current.brushing = true;
				event.currentTarget.setPointerCapture(event.pointerId);
				setHoverId(undefined);
			}
			if (current.brushing) {
				setBrush({ from: current.x, to: point.x });
				return;
			}
		}
		if (event.pointerType === "mouse") {
			setHoverId(
				findNearestPoint(layout.points, point.x, point.y, hitRadius("mouse"))
					?.run.id,
			);
		}
	};

	const onPointerUp = (event: PointerEvent<HTMLCanvasElement>) => {
		const current = gesture.current;
		gesture.current = null;
		if (!layout || current?.pointerId !== event.pointerId) return;
		const point = localPoint(event);
		if (current.brushing) {
			setBrush(undefined);
			const from = Math.min(current.x, point.x);
			const to = Math.max(current.x, point.x);
			if (to - from >= BRUSH_THRESHOLD) {
				onRangeChange?.({
					startDate: layout.x.invert(from),
					endDate: layout.x.invert(to),
				});
			}
			return;
		}
		const hit = findNearestPoint(
			layout.points,
			point.x,
			point.y,
			hitRadius(event.pointerType),
		);
		if (event.pointerType === "mouse") {
			if (hit) openRun(hit.run.id, event.metaKey || event.ctrlKey);
			else setPinnedId(undefined);
			return;
		}
		setPinnedId(hit?.run.id);
	};

	const onPointerCancel = () => {
		gesture.current = null;
		setBrush(undefined);
	};

	const onPointerLeave = (event: PointerEvent<HTMLCanvasElement>) => {
		if (event.pointerType === "mouse") setHoverId(undefined);
	};

	const onKeyDown = (event: KeyboardEvent<HTMLCanvasElement>) => {
		if (timeOrder.length === 0) return;
		const last = timeOrder.length - 1;
		const index = timeOrder.findIndex((point) => point.run.id === pinnedId);
		let next: number;
		switch (event.key) {
			case "ArrowLeft":
				next = index === -1 ? last : Math.max(0, index - 1);
				break;
			case "ArrowRight":
				next = index === -1 ? last : Math.min(last, index + 1);
				break;
			case "Home":
				next = 0;
				break;
			case "End":
				next = last;
				break;
			case "Enter":
				if (pinnedId === undefined) return;
				event.preventDefault();
				openRun(pinnedId, event.metaKey || event.ctrlKey);
				return;
			case "Escape":
				if (pinnedId === undefined) return;
				event.preventDefault();
				setPinnedId(undefined);
				return;
			default:
				return;
		}
		event.preventDefault();
		setHoverId(undefined);
		setPinnedId(timeOrder[next]?.run.id);
	};

	const hasPoints = timeOrder.length > 0;

	return (
		<div className="flex flex-col gap-3" data-testid="scatter-plot">
			<ScatterPlotLegend
				counts={legendCounts}
				selectedStateTypes={selectedStateTypes}
				onSelectedStateTypesChange={onSelectedStateTypesChange}
			/>
			<div ref={containerRef} className="relative h-52 w-full md:h-72">
				<canvas
					ref={canvasRef}
					tabIndex={hasPoints ? 0 : -1}
					role="img"
					aria-label={`Flow run durations by start time, ${summary.total.toLocaleString()} runs. Use the arrow keys to step through runs and Enter to open one.`}
					className="absolute inset-0 size-full touch-pan-y rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
					style={{ cursor: hoverId ? "pointer" : "crosshair" }}
					onPointerDown={onPointerDown}
					onPointerMove={onPointerMove}
					onPointerUp={onPointerUp}
					onPointerCancel={onPointerCancel}
					onPointerLeave={onPointerLeave}
					onKeyDown={onKeyDown}
				/>
				{layout && active && (
					<ActivePoint
						point={active}
						geometry={layout.geometry}
						radius={layout.radius}
					/>
				)}
				{layout && brush && <Brush brush={brush} geometry={layout.geometry} />}
				{history === undefined ? (
					<Skeleton className="absolute inset-0" />
				) : runs.length === 0 ? (
					<p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">
						No flow runs in this window
					</p>
				) : null}
			</div>
			{history === undefined ? (
				<Skeleton className="h-16 w-full" />
			) : (
				<ScatterPlotReadout
					run={active?.run}
					summary={summary}
					totalCount={knownTotal}
					loadedSince={since}
					upcoming={timeWindow.upcoming}
					canZoom={onRangeChange !== undefined}
				/>
			)}
		</div>
	);
};

const useElementSize = (ref: RefObject<HTMLElement | null>) => {
	const [size, setSize] = useState({ width: 0, height: 0 });
	useLayoutEffect(() => {
		const element = ref.current;
		if (!element) return;
		const measure = (width: number, height: number) =>
			setSize((current) =>
				current.width === width && current.height === height
					? current
					: { width, height },
			);
		const bounds = element.getBoundingClientRect();
		measure(bounds.width, bounds.height);
		const observer = new ResizeObserver(([entry]) => {
			if (entry) measure(entry.contentRect.width, entry.contentRect.height);
		});
		observer.observe(element);
		return () => observer.disconnect();
	}, [ref]);
	return size;
};

/** The hovered or selected run, drawn over the canvas so that moving it does
 * not repaint every point. */
const ActivePoint = ({
	point,
	geometry,
	radius,
}: {
	point: PlotPoint;
	geometry: ScatterGeometry;
	radius: number;
}) => {
	const size = (radius + 4) * 2;
	return (
		<>
			<div
				aria-hidden
				className="pointer-events-none absolute left-0 w-px bg-muted-foreground/50"
				style={{
					top: geometry.top,
					height: geometry.axisY - geometry.top,
					transform: `translateX(${Math.round(point.x)}px)`,
				}}
			/>
			<div
				aria-hidden
				className="pointer-events-none absolute top-0 left-0 rounded-full border-2 border-foreground bg-clip-content p-0.5"
				style={{
					width: size,
					height: size,
					backgroundColor: `var(--state-${point.run.state_type.toLowerCase()}-500)`,
					transform: `translate(${point.x - size / 2}px, ${point.y - size / 2}px)`,
				}}
			/>
		</>
	);
};

const Brush = ({
	brush,
	geometry,
}: {
	brush: { from: number; to: number };
	geometry: ScatterGeometry;
}) => {
	const from = Math.max(geometry.left, Math.min(brush.from, brush.to));
	const to = Math.min(geometry.right, Math.max(brush.from, brush.to));
	return (
		<div
			aria-hidden
			className="pointer-events-none absolute border-x border-foreground/60 bg-foreground/10"
			style={{
				left: from,
				width: Math.max(0, to - from),
				top: geometry.top,
				height: geometry.axisY - geometry.top,
			}}
		/>
	);
};

const readPalette = (): ScatterPalette => {
	// Color modes set their variables on <body>, below the theme on <html>.
	const style = getComputedStyle(document.body);
	const token = (name: string, fallback: string) =>
		style.getPropertyValue(name).trim() || fallback;
	return {
		border: token("--border", "#d4d4d8"),
		muted: token("--muted-foreground", "#71717a"),
		fontFamily: style.fontFamily,
		state: getAllStateColors(500),
	};
};

const useScatterPalette = () => {
	const [palette, setPalette] = useState(readPalette);
	useEffect(() => {
		const observer = new MutationObserver(() => setPalette(readPalette()));
		for (const element of [document.documentElement, document.body]) {
			observer.observe(element, {
				attributes: true,
				attributeFilter: ["class"],
			});
		}
		return () => observer.disconnect();
	}, []);
	return palette;
};
