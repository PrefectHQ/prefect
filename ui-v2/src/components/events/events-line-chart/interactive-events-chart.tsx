import type { EventsCount } from "@/api/events";
import { cn } from "@/utils";
import { EventsLineChart } from "./events-line-chart";
import { useChartZoom } from "./use-chart-zoom";

export type InteractiveEventsChartProps = {
	data: EventsCount[];
	className?: string;
	zoomStart: Date;
	zoomEnd: Date;
	onZoomChange: (start: Date, end: Date) => void;
};

/**
 * Interactive wrapper around EventsLineChart that adds zoom capabilities.
 */
export function InteractiveEventsChart({
	data,
	className,
	zoomStart,
	zoomEnd,
	onZoomChange,
}: InteractiveEventsChartProps) {
	const { containerRef, handleWheel } = useChartZoom({
		startDate: zoomStart,
		endDate: zoomEnd,
		onZoomChange,
	});

	return (
		<div
			ref={containerRef}
			role="application"
			className={cn("relative", "select-none", className)}
			onWheel={handleWheel}
		>
			<EventsLineChart
				data={data}
				className="h-full w-full"
				showAxis={false}
				zoomStart={zoomStart}
				zoomEnd={zoomEnd}
			/>
		</div>
	);
}
