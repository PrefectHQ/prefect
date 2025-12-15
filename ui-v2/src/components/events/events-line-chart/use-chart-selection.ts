import { useCallback, useRef, useState } from "react";

const MIN_SELECTION_SECONDS = 1;

export type UseChartSelectionOptions = {
	startDate: Date;
	endDate: Date;
	onSelectionChange?: (start: Date | null, end: Date | null) => void;
};

export type UseChartSelectionResult = {
	containerRef: React.RefObject<HTMLDivElement | null>;
	selectionStart: Date | null;
	selectionEnd: Date | null;
	isDragging: boolean;
	handleMouseDown: (e: React.MouseEvent) => void;
	handleMouseMove: (e: React.MouseEvent) => void;
	handleMouseUp: () => void;
	handleMouseLeave: () => void;
	clearSelection: () => void;
};

/**
 * Hook for handling drag-to-select on a chart.
 * Creates a selection range by clicking and dragging.
 *
 * @param options - Configuration options for selection behavior
 * @returns Selection state and event handlers
 */
export function useChartSelection({
	startDate,
	endDate,
	onSelectionChange,
}: UseChartSelectionOptions): UseChartSelectionResult {
	const containerRef = useRef<HTMLDivElement>(null);
	const [isDragging, setIsDragging] = useState(false);
	const [localSelectionStart, setLocalSelectionStart] = useState<Date | null>(
		null,
	);
	const [localSelectionEnd, setLocalSelectionEnd] = useState<Date | null>(null);
	const dragStartTimeRef = useRef<Date | null>(null);

	const getTimestampFromX = useCallback(
		(clientX: number): Date => {
			const container = containerRef.current;
			if (!container) return startDate;

			const rect = container.getBoundingClientRect();
			const ratio = Math.max(
				0,
				Math.min(1, (clientX - rect.left) / rect.width),
			);
			const rangeMs = endDate.getTime() - startDate.getTime();
			const timestamp = startDate.getTime() + rangeMs * ratio;

			return new Date(timestamp);
		},
		[startDate, endDate],
	);

	const getXFromTimestamp = useCallback(
		(timestamp: Date): number => {
			const container = containerRef.current;
			if (!container) return 0;

			const rect = container.getBoundingClientRect();
			const rangeMs = endDate.getTime() - startDate.getTime();
			const ratio = (timestamp.getTime() - startDate.getTime()) / rangeMs;

			return rect.left + rect.width * ratio;
		},
		[startDate, endDate],
	);

	const handleMouseDown = useCallback(
		(e: React.MouseEvent) => {
			// Only handle left mouse button
			if (e.button !== 0) return;

			const timestamp = getTimestampFromX(e.clientX);
			dragStartTimeRef.current = timestamp;
			setIsDragging(true);
			setLocalSelectionStart(timestamp);
			setLocalSelectionEnd(timestamp);
		},
		[getTimestampFromX],
	);

	const handleMouseMove = useCallback(
		(e: React.MouseEvent) => {
			if (!isDragging || !dragStartTimeRef.current) return;

			const timestamp = getTimestampFromX(e.clientX);
			const dragStartTime = dragStartTimeRef.current;
			const startX = getXFromTimestamp(dragStartTime);

			// Track both endpoints properly based on drag direction
			if (e.clientX < startX) {
				setLocalSelectionStart(timestamp);
				setLocalSelectionEnd(dragStartTime);
			} else {
				setLocalSelectionStart(dragStartTime);
				setLocalSelectionEnd(timestamp);
			}
		},
		[isDragging, getTimestampFromX, getXFromTimestamp],
	);

	const finalizeSelection = useCallback(() => {
		if (!isDragging) return;

		setIsDragging(false);

		// Check if selection is too small (less than 1 second)
		if (localSelectionStart && localSelectionEnd) {
			const selectionDurationMs = Math.abs(
				localSelectionEnd.getTime() - localSelectionStart.getTime(),
			);
			const selectionDurationSeconds = selectionDurationMs / 1000;

			if (selectionDurationSeconds < MIN_SELECTION_SECONDS) {
				// Clear selection for sub-1-second selections
				setLocalSelectionStart(null);
				setLocalSelectionEnd(null);
				onSelectionChange?.(null, null);
				return;
			}

			// Sort dates before calling onSelectionChange
			const sortedStart =
				localSelectionStart < localSelectionEnd
					? localSelectionStart
					: localSelectionEnd;
			const sortedEnd =
				localSelectionStart < localSelectionEnd
					? localSelectionEnd
					: localSelectionStart;

			onSelectionChange?.(sortedStart, sortedEnd);
		}

		dragStartTimeRef.current = null;
	}, [isDragging, localSelectionStart, localSelectionEnd, onSelectionChange]);

	const handleMouseUp = useCallback(() => {
		finalizeSelection();
	}, [finalizeSelection]);

	const handleMouseLeave = useCallback(() => {
		// Treat mouse leave as mouse up to end drag
		finalizeSelection();
	}, [finalizeSelection]);

	const clearSelection = useCallback(() => {
		setLocalSelectionStart(null);
		setLocalSelectionEnd(null);
		onSelectionChange?.(null, null);
	}, [onSelectionChange]);

	return {
		containerRef,
		selectionStart: localSelectionStart,
		selectionEnd: localSelectionEnd,
		isDragging,
		handleMouseDown,
		handleMouseMove,
		handleMouseUp,
		handleMouseLeave,
		clearSelection,
	};
}
