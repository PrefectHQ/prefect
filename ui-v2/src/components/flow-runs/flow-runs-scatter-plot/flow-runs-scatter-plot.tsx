import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import humanizeDuration from "humanize-duration";
import { Calendar, ChevronRight, Clock } from "lucide-react";
import { useMemo } from "react";
import {
	CartesianGrid,
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
import { getStateColor, STATE_COLORS } from "@/utils/state-colors";

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

type CustomDotProps = {
	cx?: number;
	cy?: number;
	payload?: ChartDataPoint;
};

const CustomDot = ({ cx, cy, payload }: CustomDotProps) => {
	if (cx === undefined || cy === undefined || !payload) {
		return null;
	}

	// Use getStateColor for dynamic color mode support
	const color =
		getStateColor(payload.stateType) ||
		STATE_COLORS[payload.stateType] ||
		"#6b7280";

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

export const formatYAxisTick = (value: number): string => {
	if (value === 0) return "0s";
	if (value < 1) return `${value.toFixed(2)}s`;

	const SECONDS_PER_YEAR = 31536000;
	const SECONDS_PER_DAY = 86400;
	const SECONDS_PER_HOUR = 3600;
	const SECONDS_PER_MINUTE = 60;

	const years = Math.floor(value / SECONDS_PER_YEAR);
	if (years > 0) return `${years}y`;

	const days = Math.floor(value / SECONDS_PER_DAY);
	if (days > 0) return `${days}d`;

	const hours = Math.floor(value / SECONDS_PER_HOUR);
	if (hours > 0) return `${hours}h`;

	const minutes = Math.floor(value / SECONDS_PER_MINUTE);
	if (minutes > 0) return `${minutes}m`;

	return `${Math.ceil(value)}s`;
};

export const TIME_INTERVALS = [
	{ ms: 1000, name: "second" },
	{ ms: 5 * 1000, name: "5seconds" },
	{ ms: 15 * 1000, name: "15seconds" },
	{ ms: 30 * 1000, name: "30seconds" },
	{ ms: 60 * 1000, name: "minute" },
	{ ms: 5 * 60 * 1000, name: "5minutes" },
	{ ms: 15 * 60 * 1000, name: "15minutes" },
	{ ms: 30 * 60 * 1000, name: "30minutes" },
	{ ms: 60 * 60 * 1000, name: "hour" },
	{ ms: 3 * 60 * 60 * 1000, name: "3hours" },
	{ ms: 6 * 60 * 60 * 1000, name: "6hours" },
	{ ms: 12 * 60 * 60 * 1000, name: "12hours" },
	{ ms: 24 * 60 * 60 * 1000, name: "day" },
	{ ms: 7 * 24 * 60 * 60 * 1000, name: "week" },
	{ ms: 30 * 24 * 60 * 60 * 1000, name: "month" },
];

export const generateNiceTimeTicks = (
	startMs: number,
	endMs: number,
	targetTickCount: number,
): number[] => {
	const range = endMs - startMs;
	if (range <= 0) return [startMs];

	const idealInterval = range / targetTickCount;
	let chosenInterval = TIME_INTERVALS[0].ms;
	for (const interval of TIME_INTERVALS) {
		if (interval.ms >= idealInterval) {
			chosenInterval = interval.ms;
			break;
		}
		chosenInterval = interval.ms;
	}

	const firstTick = Math.ceil(startMs / chosenInterval) * chosenInterval;
	const ticks: number[] = [];
	for (let tick = firstTick; tick <= endMs; tick += chosenInterval) {
		ticks.push(tick);
	}

	if (ticks.length === 0) {
		ticks.push(startMs);
	}

	return ticks;
};

export const createXAxisTickFormatter = () => {
	return (value: number): string => {
		const date = new Date(value);

		const second = new Date(date);
		second.setMilliseconds(0);
		if (second.getTime() < date.getTime()) {
			return `.${date.getMilliseconds().toString().padStart(3, "0").slice(0, 3)}`;
		}

		const minute = new Date(date);
		minute.setSeconds(0, 0);
		if (minute.getTime() < date.getTime()) {
			return `:${date.getSeconds().toString().padStart(2, "0")}`;
		}

		const hour = new Date(date);
		hour.setMinutes(0, 0, 0);
		if (hour.getTime() < date.getTime()) {
			return date.toLocaleTimeString(undefined, {
				hour: "numeric",
				minute: "2-digit",
			});
		}

		const day = new Date(date);
		day.setHours(0, 0, 0, 0);
		if (day.getTime() < date.getTime()) {
			return date.toLocaleTimeString(undefined, {
				hour: "numeric",
				hour12: true,
			});
		}

		const month = new Date(date);
		month.setDate(1);
		month.setHours(0, 0, 0, 0);
		if (month.getTime() < date.getTime()) {
			return date.toLocaleDateString(undefined, {
				weekday: "short",
				day: "numeric",
			});
		}

		const year = new Date(date);
		year.setMonth(0, 1);
		year.setHours(0, 0, 0, 0);
		if (year.getTime() < date.getTime()) {
			return date.toLocaleDateString(undefined, { month: "long" });
		}

		return date.getFullYear().toString();
	};
};

export const FlowRunsScatterPlot = ({
	history,
	startDate,
	endDate,
}: FlowRunsScatterPlotProps) => {
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

	// Compute actual numeric domain for x-axis
	const xDomain = useMemo(() => {
		if (startDate && endDate) {
			return [startDate.getTime(), endDate.getTime()] as [number, number];
		}
		if (chartData.length === 0) {
			const now = Date.now();
			const dayAgo = now - 24 * 60 * 60 * 1000;
			return [dayAgo, now] as [number, number];
		}
		// Compute from data
		const timestamps = chartData.map((d) => d.x);
		const min = Math.min(...timestamps);
		const max = Math.max(...timestamps);
		return [min, max] as [number, number];
	}, [startDate, endDate, chartData]);

	// Create memoized X-axis formatter
	const formatXAxisTick = useMemo(() => createXAxisTickFormatter(), []);

	// Generate explicit tick values for X-axis aligned with nice time boundaries
	const xAxisTicks = useMemo(() => {
		return generateNiceTimeTicks(xDomain[0], xDomain[1], 10);
	}, [xDomain]);

	if (history.length === 0) {
		return null;
	}

	return (
		<div className="hidden md:block w-full h-64" data-testid="scatter-plot">
			<ResponsiveContainer width="100%" height="100%">
				<ScatterChart>
					<CartesianGrid
						horizontal={true}
						vertical={false}
						stroke="#cacccf"
						strokeDasharray=""
					/>
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
