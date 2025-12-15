import { useCallback, useRef } from "react";

const MIN_ZOOM_SECONDS = 3599; // ~1 hour
const MAX_ZOOM_SECONDS = 604799; // ~1 week
const ZOOM_FACTOR = 0.1;

export type UseChartZoomOptions = {
	startDate: Date;
	endDate: Date;
	onZoomChange: (start: Date, end: Date) => void;
	minSeconds?: number;
	maxSeconds?: number;
};

export type UseChartZoomResult = {
	containerRef: React.RefObject<HTMLDivElement | null>;
	handleWheel: (e: React.WheelEvent) => void;
};

/**
 * Hook for handling scroll wheel zoom on a chart.
 * Zooms in/out centered on the mouse position.
 *
 * @param options - Configuration options for zoom behavior
 * @returns Container ref and wheel event handler
 */
export function useChartZoom({
	startDate,
	endDate,
	onZoomChange,
	minSeconds = MIN_ZOOM_SECONDS,
	maxSeconds = MAX_ZOOM_SECONDS,
}: UseChartZoomOptions): UseChartZoomResult {
	const containerRef = useRef<HTMLDivElement>(null);

	const handleWheel = useCallback(
		(e: React.WheelEvent) => {
			e.preventDefault();

			const container = containerRef.current;
			if (!container) return;

			const rect = container.getBoundingClientRect();
			const mouseX = e.clientX - rect.left;
			const mouseRatio = mouseX / rect.width;

			// Scroll down = zoom out (zoomDirection = 1)
			// Scroll up = zoom in (zoomDirection = -1)
			const zoomDirection = e.deltaY > 0 ? 1 : -1;

			const currentRangeMs = endDate.getTime() - startDate.getTime();
			const currentRangeSeconds = currentRangeMs / 1000;

			// Calculate new range
			const zoomAmount = currentRangeSeconds * ZOOM_FACTOR * zoomDirection;
			let newRangeSeconds = currentRangeSeconds + zoomAmount;

			// Clamp to min/max zoom levels
			newRangeSeconds = Math.max(
				minSeconds,
				Math.min(maxSeconds, newRangeSeconds),
			);

			const newRangeMs = newRangeSeconds * 1000;
			const rangeDelta = newRangeMs - currentRangeMs;

			// Distribute the range change based on mouse position
			// If mouse is at left edge (ratio=0), all change goes to end
			// If mouse is at right edge (ratio=1), all change goes to start
			const startDelta = rangeDelta * mouseRatio;
			const endDelta = rangeDelta * (1 - mouseRatio);

			let newStart = new Date(startDate.getTime() - startDelta);
			let newEnd = new Date(endDate.getTime() + endDelta);

			// Prevent zoom end from exceeding current time
			const now = new Date();
			if (newEnd > now) {
				const overflow = newEnd.getTime() - now.getTime();
				newEnd = now;
				newStart = new Date(newStart.getTime() - overflow);
			}

			onZoomChange(newStart, newEnd);
		},
		[startDate, endDate, onZoomChange, minSeconds, maxSeconds],
	);

	return {
		containerRef,
		handleWheel,
	};
}
