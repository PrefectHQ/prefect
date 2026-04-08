import { useMemo } from "react";
import type { EventsCount } from "@/api/events";
import { cn } from "@/utils";
import { EventsLineChart } from "./events-line-chart";
import { useChartSelection } from "./use-chart-selection";

export type InteractiveEventsChartProps = {
	data: EventsCount[];
	className?: string;
	startDate: Date;
	endDate: Date;
	onSelectionChange?: (start: Date, end: Date) => void;
};

/**
 * Interactive wrapper around EventsLineChart that supports
 * click-drag to select a time subrange on the chart.
 */
export function InteractiveEventsChart({
	data,
	className,
	startDate,
	endDate,
	onSelectionChange,
}: InteractiveEventsChartProps) {
	const {
		containerRef,
		selectionStart,
		selectionEnd,
		isDragging,
		handleMouseDown,
		handleMouseMove,
		handleMouseUp,
		handleMouseLeave,
	} = useChartSelection({
		startDate,
		endDate,
		onSelectionChange: (start, end) => {
			if (start && end) {
				onSelectionChange?.(start, end);
			}
		},
	});

	// Only compute overlay position while actively dragging so the highlight
	// disappears as soon as the mouse is released.
	const selectionStyle = useMemo(() => {
		if (!isDragging || !selectionStart || !selectionEnd) return null;

		const rangeMs = endDate.getTime() - startDate.getTime();
		if (rangeMs <= 0) return null;

		const leftPct =
			((selectionStart.getTime() - startDate.getTime()) / rangeMs) * 100;
		const rightPct =
			((selectionEnd.getTime() - startDate.getTime()) / rangeMs) * 100;

		return {
			left: `${Math.max(0, Math.min(leftPct, rightPct))}%`,
			width: `${Math.abs(rightPct - leftPct)}%`,
		};
	}, [isDragging, selectionStart, selectionEnd, startDate, endDate]);

	return (
		<div
			ref={containerRef}
			role="application"
			aria-label="Event chart with drag-to-select time range"
			className={cn("relative overflow-hidden", className)}
			onMouseDown={handleMouseDown}
			onMouseMove={handleMouseMove}
			onMouseUp={handleMouseUp}
			onMouseLeave={handleMouseLeave}
			style={{ cursor: isDragging ? "col-resize" : "crosshair" }}
		>
			<EventsLineChart
				data={data}
				className="h-full w-full pointer-events-none"
				showAxis={false}
				startDate={startDate}
				endDate={endDate}
			/>
			{selectionStyle && (
				<div
					className="absolute top-0 bottom-0 bg-primary/20 border-x border-primary/40"
					style={selectionStyle}
				/>
			)}
		</div>
	);
}
