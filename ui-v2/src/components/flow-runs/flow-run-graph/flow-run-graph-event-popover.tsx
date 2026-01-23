import type { EventSelection } from "@prefecthq/graphs";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { buildGetEventQuery } from "@/api/events";
import { Button } from "@/components/ui/button";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { Icon } from "@/components/ui/icons";
import { KeyValue } from "@/components/ui/key-value";

type FlowRunGraphEventPopoverProps = {
	selection: EventSelection;
	onClose: () => void;
};

export function FlowRunGraphEventPopover({
	selection,
	onClose,
}: FlowRunGraphEventPopoverProps) {
	const popoverRef = useRef<HTMLDivElement>(null);

	const { data: event, isLoading } = useQuery(
		buildGetEventQuery(selection.id, selection.occurred),
	);

	useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (
				popoverRef.current &&
				!popoverRef.current.contains(event.target as Node)
			) {
				onClose();
			}
		};

		const handleEscape = (event: KeyboardEvent) => {
			if (event.key === "Escape") {
				onClose();
			}
		};

		document.addEventListener("mousedown", handleClickOutside);
		document.addEventListener("keydown", handleEscape);

		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
			document.removeEventListener("keydown", handleEscape);
		};
	}, [onClose]);

	const position = selection.position;
	if (!position) {
		return null;
	}

	const popoverStyle = {
		position: "absolute" as const,
		left: `${position.x + position.width / 2}px`,
		top: `${position.y + position.height}px`,
		transform: "translateX(-50%)",
	};

	const eventName = event?.event ?? "Loading...";
	const resourceName =
		event?.resource?.["prefect.resource.name"] ??
		event?.resource?.["prefect.name"] ??
		event?.resource?.["prefect.resource.id"] ??
		"Unknown";

	return (
		<div
			ref={popoverRef}
			className="z-50 w-72 rounded-lg border bg-card p-4 shadow-md"
			style={popoverStyle}
		>
			<div className="flex justify-end mb-2">
				<Button
					variant="ghost"
					size="icon"
					onClick={onClose}
					aria-label="Close popover"
				>
					<Icon id="X" className="size-4" />
				</Button>
			</div>
			{isLoading ? (
				<div className="flex items-center justify-center py-4">
					<Icon id="Loader2" className="size-4 animate-spin" />
				</div>
			) : (
				<div className="space-y-3">
					<KeyValue
						label="Event"
						value={<span className="text-sm font-mono">{eventName}</span>}
					/>
					<KeyValue
						label="Occurred"
						value={<FormattedDate date={selection.occurred} />}
					/>
					<KeyValue
						label="Resource"
						value={<span className="text-sm">{resourceName}</span>}
					/>
				</div>
			)}
		</div>
	);
}
