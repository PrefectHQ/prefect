import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { formatDistanceStrict } from "date-fns";
import humanizeDuration from "humanize-duration";
import { Calendar, Clock, Loader2 } from "lucide-react";
import type { ComponentProps } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import {
	ResponsiveContainer,
	Scatter,
	ScatterChart,
	XAxis,
	YAxis,
} from "recharts";
import type { SimpleFlowRun } from "@/api/flow-runs";
import { buildGetFlowRunDetailsQuery } from "@/api/flow-runs";
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

type FlowRunTooltipContentProps = {
	flowRunId: string;
	stateType: components["schemas"]["StateType"];
	duration: number;
	timestamp: string;
};

const FlowRunTooltipContent = ({
	flowRunId,
	stateType,
	duration,
	timestamp,
}: FlowRunTooltipContentProps) => {
	const { data: flowRun, isLoading: isLoadingFlowRun } = useQuery({
		...buildGetFlowRunDetailsQuery(flowRunId),
		enabled: !!flowRunId,
	});

	const { data: flow, isLoading: isLoadingFlow } = useQuery({
		...buildFLowDetailsQuery(flowRun?.flow_id ?? ""),
		enabled: !!flowRun?.flow_id,
	});

	const startTime = new Date(timestamp);
	const isLoading = isLoadingFlowRun || isLoadingFlow;

	return (
		<div className="bg-background border rounded-lg p-3 shadow-lg flex flex-col gap-2 min-w-48">
			{isLoading ? (
				<div className="flex items-center justify-center py-2">
					<Loader2 className="size-4 animate-spin text-muted-foreground" />
				</div>
			) : (
				<>
					<div className="flex flex-col gap-0.5">
						{flow?.name && (
							<Link
								to="/flows/flow/$id"
								params={{ id: flow.id }}
								className="text-sm font-medium text-foreground hover:underline truncate max-w-48"
								title={flow.name}
							>
								{flow.name}
							</Link>
						)}
						<Link
							to="/runs/flow-run/$id"
							params={{ id: flowRunId }}
							className="text-sm text-muted-foreground hover:underline truncate max-w-48"
							title={flowRun?.name ?? flowRunId}
						>
							{flowRun?.name ?? flowRunId.slice(0, 8)}
						</Link>
					</div>
					<div>
						<StateBadge type={stateType} />
					</div>
					<hr className="border-border" />
					<div className="flex flex-col gap-1">
						<span className="flex items-center gap-2 text-sm text-muted-foreground">
							<Clock className="size-4" />
							{humanizeDuration(Math.ceil(duration * 1000), {
								largest: 2,
								round: true,
							})}
						</span>
						<span className="flex items-center gap-2 text-sm text-muted-foreground">
							<Calendar className="size-4" />
							{startTime.toLocaleString()}
						</span>
					</div>
				</>
			)}
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

type ActivePoint = {
	data: ChartDataPoint;
	x: number;
	y: number;
};

type ScatterChartMouseMove = NonNullable<
	ComponentProps<typeof ScatterChart>["onMouseMove"]
>;

export const FlowRunsScatterPlot = ({
	history,
	startDate,
	endDate,
}: FlowRunsScatterPlotProps) => {
	const [activePoint, setActivePoint] = useState<ActivePoint | null>(null);
	const [isTooltipHovered, setIsTooltipHovered] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);

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

	const handleMouseMove: ScatterChartMouseMove = useCallback((state) => {
		// Type assertion needed because Recharts types activePayload as an error type
		const activePayload = state.activePayload as
			| Array<{ payload?: ChartDataPoint }>
			| undefined;
		const activeCoordinate = state.activeCoordinate;

		if (activePayload && activePayload.length > 0 && activeCoordinate) {
			const point = activePayload[0]?.payload;
			if (point && typeof point === "object" && "id" in point) {
				setActivePoint({
					data: point,
					x: activeCoordinate.x,
					y: activeCoordinate.y,
				});
			}
		}
	}, []);

	const handleMouseLeave = useCallback(() => {
		// Delay hiding to allow moving to tooltip
		setTimeout(() => {
			if (!isTooltipHovered) {
				setActivePoint(null);
			}
		}, 100);
	}, [isTooltipHovered]);

	const handleTooltipMouseEnter = useCallback(() => {
		setIsTooltipHovered(true);
	}, []);

	const handleTooltipMouseLeave = useCallback(() => {
		setIsTooltipHovered(false);
		setActivePoint(null);
	}, []);

	if (history.length === 0) {
		return null;
	}

	return (
		<div
			ref={containerRef}
			className="hidden md:block w-full h-64 relative"
			data-testid="scatter-plot"
		>
			<ResponsiveContainer width="100%" height="100%">
				<ScatterChart
					margin={{ top: 20, right: 20, bottom: 20, left: 40 }}
					onMouseMove={handleMouseMove}
					onMouseLeave={handleMouseLeave}
				>
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
					<Scatter
						data={chartData}
						shape={<CustomDot />}
						isAnimationActive={false}
					/>
				</ScatterChart>
			</ResponsiveContainer>
			{activePoint && (
				<div
					role="tooltip"
					className="absolute z-50 pointer-events-auto"
					style={{
						left: activePoint.x + 10,
						top: activePoint.y - 10,
					}}
					onMouseEnter={handleTooltipMouseEnter}
					onMouseLeave={handleTooltipMouseLeave}
				>
					<FlowRunTooltipContent
						flowRunId={activePoint.data.id}
						stateType={activePoint.data.stateType}
						duration={activePoint.data.duration}
						timestamp={activePoint.data.timestamp}
					/>
				</div>
			)}
		</div>
	);
};
