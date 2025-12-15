import { useCallback, useMemo } from "react";
import type { EventsCount } from "@/api/events";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils";
import { EventsLineChart } from "./events-line-chart";
import { useChartSelection } from "./use-chart-selection";
import { useChartZoom } from "./use-chart-zoom";

export type InteractiveEventsChartProps = {
	data: EventsCount[];
	className?: string;
	zoomStart: Date;
	zoomEnd: Date;
	onZoomChange: (start: Date, end: Date) => void;
	onSelectionChange?: (start: Date | null, end: Date | null) => void;
	selectionStart?: Date | null;
	selectionEnd?: Date | null;
};

/**
 * Interactive wrapper around EventsLineChart that adds zoom and selection capabilities.
 * Supports both controlled and uncontrolled selection modes.
 */
export function InteractiveEventsChart({
	data,
	className,
	zoomStart,
	zoomEnd,
	onZoomChange,
	onSelectionChange,
	selectionStart: controlledSelectionStart,
	selectionEnd: controlledSelectionEnd,
}: InteractiveEventsChartProps) {
	const { containerRef: zoomContainerRef, handleWheel } = useChartZoom({
		startDate: zoomStart,
		endDate: zoomEnd,
		onZoomChange,
	});

	const {
		containerRef: selectionContainerRef,
		selectionStart: localSelectionStart,
		selectionEnd: localSelectionEnd,
		isDragging,
		handleMouseDown,
		handleMouseMove,
		handleMouseUp,
		handleMouseLeave,
		clearSelection,
	} = useChartSelection({
		startDate: zoomStart,
		endDate: zoomEnd,
		onSelectionChange,
	});

	// Merge refs from both hooks so they both reference the same DOM element
	const mergedRef = useCallback(
		(node: HTMLDivElement | null) => {
			// Set the ref for both hooks
			(
				zoomContainerRef as React.MutableRefObject<HTMLDivElement | null>
			).current = node;
			(
				selectionContainerRef as React.MutableRefObject<HTMLDivElement | null>
			).current = node;
		},
		[zoomContainerRef, selectionContainerRef],
	);

	// Support both controlled and uncontrolled selection modes via fallback pattern
	const selectionStart = controlledSelectionStart ?? localSelectionStart;
	const selectionEnd = controlledSelectionEnd ?? localSelectionEnd;

	const hasSelection = selectionStart !== null && selectionEnd !== null;
	const showClearButton = hasSelection && !isDragging;

	const handleClearSelection = useCallback(() => {
		clearSelection();
	}, [clearSelection]);

	const handleClearButtonMouseDown = useCallback((e: React.MouseEvent) => {
		e.stopPropagation();
	}, []);

	// Memoize the container style to avoid unnecessary re-renders
	const containerClassName = useMemo(
		() =>
			cn(
				"relative",
				isDragging && "cursor-crosshair",
				"select-none",
				className,
			),
		[isDragging, className],
	);

	return (
		<div
			ref={mergedRef}
			role="application"
			className={containerClassName}
			onWheel={handleWheel}
			onMouseDown={handleMouseDown}
			onMouseMove={handleMouseMove}
			onMouseUp={handleMouseUp}
			onMouseLeave={handleMouseLeave}
		>
			<EventsLineChart
				data={data}
				className="h-full w-full"
				selectionStart={selectionStart}
				selectionEnd={selectionEnd}
			/>
			{showClearButton && (
				<div className="absolute top-2 right-2">
					<Button
						variant="outline"
						size="sm"
						onClick={handleClearSelection}
						onMouseDown={handleClearButtonMouseDown}
					>
						Clear selection
					</Button>
				</div>
			)}
		</div>
	);
}
