import type { StateSelection } from "@prefecthq/graphs";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { Icon } from "@/components/ui/icons";
import { KeyValue } from "@/components/ui/key-value";
import { StateBadge } from "@/components/ui/state-badge";

type FlowRunGraphStatePopoverProps = {
	selection: StateSelection;
	onClose: () => void;
};

export function FlowRunGraphStatePopover({
	selection,
	onClose,
}: FlowRunGraphStatePopoverProps) {
	const popoverRef = useRef<HTMLDivElement>(null);

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

	return (
		<div
			ref={popoverRef}
			className="z-50 w-64 rounded-lg border bg-card p-4 shadow-md"
			style={popoverStyle}
		>
			<div className="flex justify-end absolute top-2 right-2">
				<Button
					variant="ghost"
					size="icon"
					onClick={onClose}
					aria-label="Close popover"
				>
					<Icon id="X" className="size-4" />
				</Button>
			</div>
			<div className="space-y-3">
				<KeyValue
					label="State"
					value={<StateBadge type={selection.type} name={selection.name} />}
				/>
				<KeyValue
					label="Occurred"
					value={
						<FormattedDate date={selection.timestamp} format="timestamp" />
					}
				/>
			</div>
		</div>
	);
}
