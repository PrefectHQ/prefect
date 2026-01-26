import type { EventsSelection } from "@prefecthq/graphs";
import { useQueries } from "@tanstack/react-query";
import { buildGetEventQuery } from "@/api/events";
import { Button } from "@/components/ui/button";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { Icon } from "@/components/ui/icons";
import {
	Popover,
	PopoverAnchor,
	PopoverContent,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

type FlowRunGraphEventsPopoverProps = {
	selection: EventsSelection;
	onClose: () => void;
};

export function FlowRunGraphEventsPopover({
	selection,
	onClose,
}: FlowRunGraphEventsPopoverProps) {
	const eventQueries = useQueries({
		queries: selection.ids.map((id) =>
			buildGetEventQuery(id, selection.occurred ?? new Date()),
		),
	});

	const position = selection.position;
	if (!position) {
		return null;
	}

	const anchorStyle = {
		position: "absolute" as const,
		left: `${position.x + position.width / 2}px`,
		top: `${position.y + position.height}px`,
	};

	const isLoading = eventQueries.some((q) => q.isLoading);
	const events = eventQueries
		.map((q) => q.data)
		.filter((e): e is NonNullable<typeof e> => e !== undefined);

	return (
		<Popover open onOpenChange={(open) => !open && onClose()}>
			<PopoverAnchor style={anchorStyle} />
			<PopoverContent align="center" side="bottom" className="w-80">
				<div className="flex items-center justify-between mb-2">
					<span className="text-sm font-medium">
						{selection.ids.length} Events
					</span>
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
					<ScrollArea className="max-h-64">
						<div className="space-y-3">
							{events.map((event) => (
								<div
									key={event.id}
									className="border-b pb-2 last:border-b-0 last:pb-0"
								>
									<div
										className="text-sm font-mono truncate"
										title={event.event}
									>
										{event.event}
									</div>
									<div className="text-xs text-muted-foreground">
										<FormattedDate date={new Date(event.occurred)} />
									</div>
								</div>
							))}
						</div>
					</ScrollArea>
				)}
			</PopoverContent>
		</Popover>
	);
}
