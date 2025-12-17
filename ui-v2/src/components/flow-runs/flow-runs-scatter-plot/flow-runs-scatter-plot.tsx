import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { formatDistanceStrict } from "date-fns";
import humanizeDuration from "humanize-duration";
import { Calendar, ChevronRight, Clock } from "lucide-react";
import { useMemo } from "react";
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

const formatYAxisTick = (value: number): string => {
	if (value === 0) return "0s";
	return formatDistanceStrict(0, value * 1000, { addSuffix: false });
};

const formatXAxisTick = (value: number): string => {
	const date = new Date(value);
	return date.toLocaleDateString(undefined, {
		month: "short",
		day: "numeric",
	});
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

	const xDomain = useMemo(() => {
		if (startDate && endDate) {
			return [startDate.getTime(), endDate.getTime()];
		}
		if (chartData.length === 0) {
			const now = Date.now();
			const dayAgo = now - 24 * 60 * 60 * 1000;
			return [dayAgo, now];
		}
		return ["dataMin", "dataMax"] as const;
	}, [startDate, endDate, chartData.length]);

	if (history.length === 0) {
		return null;
	}

	return (
		<div className="hidden md:block w-full h-64" data-testid="scatter-plot">
			<ResponsiveContainer width="100%" height="100%">
				<ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 40 }}>
					<XAxis
						type="number"
						dataKey="x"
						scale="time"
						domain={xDomain}
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
