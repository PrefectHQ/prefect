import { format } from "date-fns";
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import { Area, AreaChart, XAxis, YAxis } from "recharts";
import type { EventsCount } from "@/api/events";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { cn } from "@/utils";

type ChartDataPoint = {
	time: number;
	count: number;
	label: string;
};

type EventsTooltipProps = {
	active?: boolean;
	payload?: Array<{ payload?: ChartDataPoint }>;
};

const EventsTooltipContent = ({ active, payload }: EventsTooltipProps) => {
	if (!active || !payload || !payload.length) return null;

	const firstPayloadItem = payload[0];
	const point = firstPayloadItem?.payload;

	if (
		!point ||
		typeof point.time !== "number" ||
		typeof point.count !== "number"
	) {
		return null;
	}

	return (
		<div className="bg-popover border rounded-lg p-2 shadow-md">
			<div className="text-sm font-medium">{point.count} events</div>
			<div className="text-xs text-muted-foreground">
				{format(new Date(point.time), "PPp")}
			</div>
		</div>
	);
};

export type EventsLineChartProps = {
	data: EventsCount[];
	className?: string;
	/** Whether to show the X-axis with time labels (default: true) */
	showAxis?: boolean;
	/** Date range start for chart display */
	startDate?: Date;
	/** Date range end for chart display */
	endDate?: Date;
	/** Called when mouse hovers over chart with timestamp */
	onCursorChange?: (timestamp: Date | null) => void;
};

export type EventsLineChartRef = {
	clearSelection: () => void;
};

const chartConfig = {
	count: {
		label: "Events",
		color: "hsl(262.1 83.3% 57.8%)",
	},
};

export const EventsLineChart = forwardRef<
	EventsLineChartRef,
	EventsLineChartProps
>(function EventsLineChart(
	{ data, className, showAxis = true, startDate, endDate, onCursorChange },
	ref,
) {
	const containerRef = useRef<HTMLDivElement>(null);

	useImperativeHandle(ref, () => ({
		clearSelection: () => {
			// Selection clearing logic handled by parent
		},
	}));

	const chartData = useMemo(() => {
		const points = data.map((item) => ({
			time: new Date(item.start_time).getTime(),
			count: item.count,
			label: item.label,
		}));

		// Ensure we have boundary points at startDate and endDate so the line
		// extends across the full chart width (matching Vue implementation)
		if (startDate && endDate) {
			const startTime = startDate.getTime();
			const endTime = endDate.getTime();

			// Add start boundary point if not present
			if (points.length === 0 || points[0].time > startTime) {
				points.unshift({ time: startTime, count: 0, label: "" });
			}

			// Add end boundary point if not present
			if (points.length === 0 || points[points.length - 1].time < endTime) {
				points.push({ time: endTime, count: 0, label: "" });
			}
		}

		return points;
	}, [data, startDate, endDate]);

	const handleMouseMove = (state: { activeLabel?: string | number }) => {
		if (state.activeLabel !== undefined && onCursorChange) {
			const timestamp =
				typeof state.activeLabel === "number"
					? state.activeLabel
					: Number(state.activeLabel);
			if (!Number.isNaN(timestamp)) {
				onCursorChange(new Date(timestamp));
			}
		}
	};

	const handleMouseLeave = () => {
		onCursorChange?.(null);
	};

	return (
		<div ref={containerRef} className={cn("relative", className)}>
			<ChartContainer
				config={chartConfig}
				className="h-full w-[calc(100%+3rem)] -mx-6"
			>
				<AreaChart
					data={chartData}
					margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
					onMouseMove={handleMouseMove}
					onMouseLeave={handleMouseLeave}
				>
					<defs>
						<linearGradient id="eventsGradient" x1="0" y1="0" x2="0" y2="1">
							<stop
								offset="0%"
								stopColor="var(--color-count)"
								stopOpacity={0.3}
							/>
							<stop
								offset="100%"
								stopColor="var(--color-count)"
								stopOpacity={0}
							/>
						</linearGradient>
					</defs>
					<XAxis
						dataKey="time"
						tickFormatter={(value: number) => format(new Date(value), "HH:mm")}
						tick={{ fontSize: 12 }}
						axisLine={false}
						tickLine={false}
						domain={["dataMin", "dataMax"]}
						hide={!showAxis}
					/>
					<YAxis hide domain={[0, (max: number) => Math.max(1, max)]} />
					<ChartTooltip content={<EventsTooltipContent />} />
					<Area
						type="monotone"
						dataKey="count"
						stroke="var(--color-count)"
						strokeWidth={2}
						fill="url(#eventsGradient)"
						dot={false}
						activeDot={false}
						isAnimationActive={false}
					/>
				</AreaChart>
			</ChartContainer>
		</div>
	);
});
