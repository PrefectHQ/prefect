import type { EventSelection } from "@prefecthq/graphs";
import { useQuery } from "@tanstack/react-query";
import { buildGetEventQuery } from "@/api/events";
import { Button } from "@/components/ui/button";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { Icon } from "@/components/ui/icons";
import { KeyValue } from "@/components/ui/key-value";
import {
	Popover,
	PopoverAnchor,
	PopoverContent,
} from "@/components/ui/popover";

type FlowRunGraphEventPopoverProps = {
	selection: EventSelection;
	onClose: () => void;
};

export function FlowRunGraphEventPopover({
	selection,
	onClose,
}: FlowRunGraphEventPopoverProps) {
	const { data: event, isLoading } = useQuery(
		buildGetEventQuery(selection.id, selection.occurred),
	);

	const position = selection.position;
	if (!position) {
		return null;
	}

	const anchorStyle = {
		position: "absolute" as const,
		left: `${position.x + position.width / 2}px`,
		top: `${position.y + position.height}px`,
	};

	const eventName = event?.event ?? "Loading...";
	const resourceName =
		event?.resource?.["prefect.resource.name"] ??
		event?.resource?.["prefect.name"] ??
		event?.resource?.["prefect.resource.id"] ??
		"Unknown";

	return (
		<Popover open onOpenChange={(open) => !open && onClose()}>
			<PopoverAnchor style={anchorStyle} />
			<PopoverContent align="center" side="bottom" className="w-72">
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
			</PopoverContent>
		</Popover>
	);
}
