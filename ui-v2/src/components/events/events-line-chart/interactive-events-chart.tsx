import type { EventsCount } from "@/api/events";
import { cn } from "@/utils";
import { EventsLineChart } from "./events-line-chart";

export type InteractiveEventsChartProps = {
	data: EventsCount[];
	className?: string;
	startDate: Date;
	endDate: Date;
};

/**
 * Interactive wrapper around EventsLineChart.
 */
export function InteractiveEventsChart({
	data,
	className,
	startDate,
	endDate,
}: InteractiveEventsChartProps) {
	return (
		<div className={cn("relative", className)}>
			<EventsLineChart
				data={data}
				className="h-full w-full"
				showAxis={false}
				startDate={startDate}
				endDate={endDate}
			/>
		</div>
	);
}
