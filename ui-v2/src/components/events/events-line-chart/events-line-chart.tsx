import { format } from "date-fns";
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import { Area, AreaChart, ReferenceArea, XAxis, YAxis } from "recharts";
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
	/** Current zoom range start */
	zoomStart?: Date;
	/** Current zoom range end */
	zoomEnd?: Date;
	/** Selection range start (for filtering) */
	selectionStart?: Date | null;
	/** Selection range end (for filtering) */
	selectionEnd?: Date | null;
	/** Called when zoom range changes (via scroll wheel) */
	onZoomChange?: (start: Date, end: Date) => void;
	/** Called when selection range changes (via drag) */
	onSelectionChange?: (start: Date | null, end: Date | null) => void;
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
	{
		data,
		className,
		showAxis = true,
		zoomStart,
		zoomEnd,
		selectionStart,
		selectionEnd,
		onCursorChange,
	},
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

		// Ensure we have boundary points at zoomStart and zoomEnd so the line
		// extends across the full chart width (matching Vue implementation)
		if (zoomStart && zoomEnd) {
			const startTime = zoomStart.getTime();
			const endTime = zoomEnd.getTime();

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
	}, [data, zoomStart, zoomEnd]);

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

	// Calculate selection area bounds
	const selectionArea = useMemo(() => {
		if (!selectionStart || !selectionEnd) return null;
		return {
			x1: selectionStart.getTime(),
			x2: selectionEnd.getTime(),
		};
	}, [selectionStart, selectionEnd]);

	return (
		<div ref={containerRef} className={cn("relative", className)}>
			<ChartContainer config={chartConfig} className="h-full w-full">
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
					{/* Selection highlight area */}
					{selectionArea && (
						<ReferenceArea
							x1={selectionArea.x1}
							x2={selectionArea.x2}
							fill="hsl(var(--primary))"
							fillOpacity={0.2}
							stroke="hsl(var(--primary))"
							strokeOpacity={0.5}
						/>
					)}
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
