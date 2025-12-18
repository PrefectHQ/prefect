import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { formatDistanceStrict } from "date-fns";
import humanizeDuration from "humanize-duration";
import { Calendar, ChevronRight, Clock } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
	ResponsiveContainer,
	Scatter,
	ScatterChart,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	buildGetFlowRunDetailsQuery,
	type SimpleFlowRun,
} from "@/api/flow-runs";
import { buildFLowDetailsQuery } from "@/api/flows";
import type { components } from "@/api/prefect";
import { StateBadge } from "@/components/ui/state-badge";

type FlowRunsScatterPlotProps = {
	history: SimpleFlowRun[];
	startDate?: Date;
	endDate?: Date;
};

type ChartDataPoint = {
	x: number;
	y: number;
	stateType: components["schemas"]["StateType"];
	id: string;
	duration: number;
	lateness: number;
	timestamp: string;
};

const STATE_COLORS: Record<components["schemas"]["StateType"], string> = {
	COMPLETED: "#16a34a", // green-600
	FAILED: "#dc2626", // red-600
	RUNNING: "#1d4ed8", // blue-700
	CANCELLED: "#6b7280", // gray-500
	CANCELLING: "#4b5563", // gray-600
	CRASHED: "#ea580c", // orange-600
	PAUSED: "#6b7280", // gray-500
	PENDING: "#9ca3af", // gray-400
	SCHEDULED: "#facc15", // yellow-400
};

type CustomDotProps = {
	cx?: number;
	cy?: number;
	payload?: ChartDataPoint;
};

const CustomDot = ({ cx, cy, payload }: CustomDotProps) => {
	if (cx === undefined || cy === undefined || !payload) {
		return null;
	}

	const color = STATE_COLORS[payload.stateType] || "#6b7280";

	return (
		<circle
			cx={cx}
			cy={cy}
			r={6}
			fill={color}
			stroke={color}
			strokeWidth={1}
			opacity={0.7}
			className="hover:opacity-100 transition-opacity cursor-pointer"
		/>
	);
};

type FlowRunTooltipPayload = {
	payload?: ChartDataPoint;
};

type FlowRunTooltipProps = {
	active?: boolean;
	payload?: FlowRunTooltipPayload[];
};

const FlowRunTooltip = ({ active, payload }: FlowRunTooltipProps) => {
	const firstPayload = payload?.[0];
	const data = firstPayload?.payload;
	const flowRunId = data?.id;

	// Fetch flow run details when tooltip is active
	const { data: flowRun } = useQuery({
		...buildGetFlowRunDetailsQuery(flowRunId ?? ""),
		enabled: active && Boolean(flowRunId),
		staleTime: 5 * 60 * 1000, // 5 minutes to avoid refetching on mouse movement
	});

	// Fetch flow details when we have flow_id
	const { data: flow } = useQuery({
		...buildFLowDetailsQuery(flowRun?.flow_id ?? ""),
		enabled: Boolean(flowRun?.flow_id),
		staleTime: 5 * 60 * 1000,
	});

	if (!active || !payload || payload.length === 0 || !data) {
		return null;
	}

	const startTime = new Date(data.timestamp);

	return (
		<div className="bg-background border rounded-lg p-3 shadow-lg flex flex-col gap-2 min-w-48">
			{/* Flow name and flow run name breadcrumbs */}
			<div className="flex items-center gap-1 text-sm text-muted-foreground">
				{flowRun?.flow_id && (
					<>
						<Link
							to="/flows/flow/$id"
							params={{ id: flowRun.flow_id }}
							className="font-semibold hover:underline truncate max-w-32"
						>
							{flow?.name ?? "..."}
						</Link>
						<ChevronRight className="size-3 flex-shrink-0" />
					</>
				)}
				<Link
					to="/runs/flow-run/$id"
					params={{ id: data.id }}
					className="hover:underline truncate max-w-32"
				>
					{flowRun?.name ?? data.id.slice(0, 8)}
				</Link>
			</div>
			<div>
				<StateBadge type={data.stateType} />
			</div>
			<hr className="border-border" />
			<div className="flex flex-col gap-1">
				<span className="flex items-center gap-2 text-sm text-muted-foreground">
					<Clock className="size-4" />
					{humanizeDuration(Math.ceil(data.duration * 1000), {
						largest: 2,
						round: true,
					})}
				</span>
				<span className="flex items-center gap-2 text-sm text-muted-foreground">
					<Calendar className="size-4" />
					{startTime.toLocaleString()}
				</span>
			</div>
		</div>
	);
};

const createYAxisTickFormatter = (maxDuration: number) => {
	return (value: number): string => {
		if (value === 0) return "0s";
		// For very small durations (< 1 second), show milliseconds
		if (maxDuration < 1) {
			return `${Math.round(value * 1000)}ms`;
		}
		// For small durations (< 10 seconds), show one decimal
		if (maxDuration < 10) {
			return `${value.toFixed(1)}s`;
		}
		// For durations < 60 seconds, show integer seconds
		if (maxDuration < 60) {
			return `${Math.round(value)}s`;
		}
		// For larger durations, use the humanized format
		return formatDistanceStrict(0, value * 1000, { addSuffix: false });
	};
};

const createXAxisTickFormatter = (rangeMs: number, minDeltaMs: number) => {
	const oneMinute = 60 * 1000;
	const oneHour = 60 * oneMinute;
	const oneDay = 24 * oneHour;

	return (value: number): string => {
		const date = new Date(value);

		// If data points are very close (< 1 second apart) or range is very small, show with fractional seconds
		if (minDeltaMs < 1000 || rangeMs < 10_000) {
			const seconds = date.getSeconds();
			const ms = date.getMilliseconds();
			const timeStr = date.toLocaleTimeString(undefined, {
				hour: "2-digit",
				minute: "2-digit",
			});
			// Append seconds and tenths of a second
			return `${timeStr}:${seconds.toString().padStart(2, "0")}.${Math.floor(ms / 100)}`;
		}

		// If data points are within a minute apart or range is small, show with seconds
		if (minDeltaMs < oneMinute || rangeMs < 10 * oneMinute) {
			return date.toLocaleTimeString(undefined, {
				hour: "2-digit",
				minute: "2-digit",
				second: "2-digit",
			});
		}

		// For multi-day ranges, show date on day boundaries (midnight) and time otherwise
		// This follows the Vue implementation pattern from formatLabel
		if (rangeMs >= oneDay) {
			// Check if this tick falls on a day boundary (midnight)
			const isStartOfDay =
				date.getHours() === 0 &&
				date.getMinutes() === 0 &&
				date.getSeconds() === 0 &&
				date.getMilliseconds() === 0;

			if (isStartOfDay) {
				// Show date for day boundaries (e.g., "Mon 15" or "Dec 15")
				return date.toLocaleDateString(undefined, {
					weekday: "short",
					day: "numeric",
				});
			}

			// Show time for non-boundary ticks
			return date.toLocaleTimeString(undefined, {
				hour: "2-digit",
				minute: "2-digit",
			});
		}

		// If range is less than a day, show time (hours and minutes)
		return date.toLocaleTimeString(undefined, {
			hour: "2-digit",
			minute: "2-digit",
		});
	};
};

export const FlowRunsScatterPlot = ({
	history,
	startDate,
	endDate,
}: FlowRunsScatterPlotProps) => {
	const containerRef = useRef<HTMLDivElement>(null);
	const [containerWidth, setContainerWidth] = useState(0);

	// Track container width for dynamic tick count calculation
	useEffect(() => {
		const container = containerRef.current;
		if (!container) return;

		const resizeObserver = new ResizeObserver((entries) => {
			for (const entry of entries) {
				setContainerWidth(entry.contentRect.width);
			}
		});

		resizeObserver.observe(container);
		// Set initial width
		setContainerWidth(container.getBoundingClientRect().width);

		return () => resizeObserver.disconnect();
	}, []);

	const chartData = useMemo<ChartDataPoint[]>(() => {
		return history.map((item) => ({
			x: new Date(item.timestamp).getTime(),
			y: item.duration,
			stateType: item.state_type,
			id: item.id,
			duration: item.duration,
			lateness: item.lateness,
			timestamp: item.timestamp,
		}));
	}, [history]);

	// Compute actual numeric domain for x-axis (needed for adaptive formatting)
	const { xDomain, xDomainMin, xDomainMax } = useMemo(() => {
		if (startDate && endDate) {
			return {
				xDomain: [startDate.getTime(), endDate.getTime()] as [number, number],
				xDomainMin: startDate.getTime(),
				xDomainMax: endDate.getTime(),
			};
		}
		if (chartData.length === 0) {
			const now = Date.now();
			const dayAgo = now - 24 * 60 * 60 * 1000;
			return {
				xDomain: [dayAgo, now] as [number, number],
				xDomainMin: dayAgo,
				xDomainMax: now,
			};
		}
		// Compute from data
		const timestamps = chartData.map((d) => d.x);
		const min = Math.min(...timestamps);
		const max = Math.max(...timestamps);
		return {
			xDomain: [min, max] as [number, number],
			xDomainMin: min,
			xDomainMax: max,
		};
	}, [startDate, endDate, chartData]);

	// Compute max duration for adaptive y-axis formatting
	const maxDuration = useMemo(() => {
		if (chartData.length === 0) return 60;
		return Math.max(...chartData.map((d) => d.y));
	}, [chartData]);

	// Compute minimum delta between data points for adaptive x-axis formatting
	const minDeltaMs = useMemo(() => {
		if (chartData.length < 2) return Number.POSITIVE_INFINITY;
		const sortedTimestamps = chartData.map((d) => d.x).sort((a, b) => a - b);
		let minDelta = Number.POSITIVE_INFINITY;
		for (let i = 1; i < sortedTimestamps.length; i++) {
			const delta = sortedTimestamps[i] - sortedTimestamps[i - 1];
			if (delta > 0 && delta < minDelta) {
				minDelta = delta;
			}
		}
		return minDelta;
	}, [chartData]);

	// Create memoized formatters based on domain
	const rangeMs = xDomainMax - xDomainMin;
	const formatXAxisTick = useMemo(
		() => createXAxisTickFormatter(rangeMs, minDeltaMs),
		[rangeMs, minDeltaMs],
	);

	const formatYAxisTick = useMemo(
		() => createYAxisTickFormatter(maxDuration),
		[maxDuration],
	);

	// Calculate explicit tick values for evenly spaced x-axis ticks
	// Target ~100px spacing between ticks for visually even distribution
	// For multi-day ranges, include midnight boundaries to show day changes
	const xAxisTicks = useMemo(() => {
		const tickSpacing = 100; // pixels between ticks
		const chartMargin = 60; // left (40) + right (20) margins from ScatterChart
		const availableWidth = containerWidth - chartMargin;
		const tickCount = Math.max(2, Math.ceil(availableWidth / tickSpacing));

		const oneDay = 24 * 60 * 60 * 1000;
		const rangeMs = xDomainMax - xDomainMin;

		// For multi-day ranges, generate ticks that include midnight boundaries
		if (rangeMs >= oneDay) {
			const ticks: number[] = [];

			// Find the first midnight after xDomainMin
			const startDate = new Date(xDomainMin);
			const firstMidnight = new Date(startDate);
			firstMidnight.setHours(24, 0, 0, 0); // Next midnight

			// Add start tick
			ticks.push(xDomainMin);

			// Add midnight boundaries
			let currentMidnight = firstMidnight.getTime();
			while (currentMidnight < xDomainMax) {
				ticks.push(currentMidnight);
				currentMidnight += oneDay;
			}

			// Add end tick if not too close to last tick
			const lastTick = ticks[ticks.length - 1];
			if (xDomainMax - lastTick > rangeMs / tickCount / 2) {
				ticks.push(xDomainMax);
			}

			// If we have too few ticks, add intermediate ticks between midnights
			if (ticks.length < tickCount) {
				const newTicks: number[] = [];
				for (let i = 0; i < ticks.length - 1; i++) {
					newTicks.push(ticks[i]);
					const gap = ticks[i + 1] - ticks[i];
					const intermediateCount = Math.max(
						1,
						Math.floor(gap / (rangeMs / tickCount)),
					);
					if (intermediateCount > 1) {
						const intermediateStep = gap / intermediateCount;
						for (let j = 1; j < intermediateCount; j++) {
							newTicks.push(ticks[i] + intermediateStep * j);
						}
					}
				}
				newTicks.push(ticks[ticks.length - 1]);
				return newTicks;
			}

			return ticks;
		}

		// For single-day ranges, generate evenly spaced ticks
		const ticks: number[] = [];
		const step = (xDomainMax - xDomainMin) / (tickCount - 1);
		for (let i = 0; i < tickCount; i++) {
			ticks.push(xDomainMin + step * i);
		}
		return ticks;
	}, [containerWidth, xDomainMin, xDomainMax]);

	if (history.length === 0) {
		return null;
	}

	return (
		<div
			ref={containerRef}
			className="hidden md:block w-full h-64"
			data-testid="scatter-plot"
		>
			<ResponsiveContainer width="100%" height="100%">
				<ScatterChart>
					<XAxis
						type="number"
						dataKey="x"
						scale="time"
						domain={xDomain}
						ticks={xAxisTicks}
						tickFormatter={formatXAxisTick}
						tick={{ fontSize: 12 }}
						tickLine={false}
						axisLine={{ stroke: "#e5e7eb" }}
					/>
					<YAxis
						type="number"
						dataKey="y"
						tickFormatter={formatYAxisTick}
						tick={{ fontSize: 12 }}
						tickLine={false}
						axisLine={{ stroke: "#e5e7eb" }}
						width={60}
					/>
					<Tooltip
						content={<FlowRunTooltip />}
						cursor={{ strokeDasharray: "3 3" }}
						animationDuration={0}
					/>
					<Scatter
						data={chartData}
						shape={<CustomDot />}
						isAnimationActive={false}
					/>
				</ScatterChart>
			</ResponsiveContainer>
		</div>
	);
};
