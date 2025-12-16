import { format, formatDistanceToNow } from "date-fns";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { JsonView } from "@/components/ui/json-view";
import { cn } from "@/utils";
import { EventResourceDisplay } from "../event-resource-display";
import { formatEventLabel } from "./utilities";

type Event = components["schemas"]["ReceivedEvent"];

type EventsTimelineProps = {
	events: Event[];
	onEventClick?: (eventName: string) => void;
	onResourceClick?: (resourceId: string) => void;
	onFilterEventsSince?: (date: Date) => void;
	onFilterEventsUntil?: (date: Date) => void;
	className?: string;
};

type EventTimelineItemProps = {
	event: Event;
	onEventClick?: (eventName: string) => void;
	onResourceClick?: (resourceId: string) => void;
	onFilterEventsSince?: (date: Date) => void;
	onFilterEventsUntil?: (date: Date) => void;
};

function EventTimestamp({ occurred }: { occurred: string }) {
	const date = new Date(occurred);
	const formattedDate = format(date, "MMM d, yyyy HH:mm:ss");
	const relativeTime = formatDistanceToNow(date, { addSuffix: true });

	return (
		<div className="flex flex-col text-xs text-muted-foreground">
			<span>{formattedDate}</span>
			<span>{relativeTime}</span>
		</div>
	);
}

function EventNameWithPrefixes({
	eventName,
	onEventClick,
}: {
	eventName: string;
	onEventClick?: (eventName: string) => void;
}) {
	const label = formatEventLabel(eventName);

	return (
		<div className="flex flex-col gap-0.5">
			{onEventClick ? (
				<button
					type="button"
					onClick={() => onEventClick(eventName)}
					className="text-left font-medium hover:underline"
				>
					{label}
				</button>
			) : (
				<span className="font-medium">{label}</span>
			)}
			<span className="text-xs text-muted-foreground font-mono">
				{eventName}
			</span>
		</div>
	);
}

function getResourceRole(resource: Record<string, string>): string | undefined {
	return resource["prefect.resource.role"];
}

function getResourceId(resource: Record<string, string>): string {
	return resource["prefect.resource.id"] || "";
}

function getResourceName(resource: Record<string, string>): string | null {
	return (
		resource["prefect.resource.name"] ||
		resource["prefect.name"] ||
		resource["prefect-cloud.name"] ||
		null
	);
}

function EventRelatedResources({
	related,
	onResourceClick,
}: {
	related: components["schemas"]["RelatedResource"][];
	onResourceClick?: (resourceId: string) => void;
}) {
	if (!related || related.length === 0) {
		return null;
	}

	// Separate tags from other resources
	const tags: components["schemas"]["RelatedResource"][] = [];
	const resources: components["schemas"]["RelatedResource"][] = [];

	for (const resource of related) {
		const role = getResourceRole(resource);
		if (role === "tag") {
			tags.push(resource);
		} else {
			resources.push(resource);
		}
	}

	return (
		<div className="flex flex-col gap-2">
			<span className="text-sm font-medium">Related Resources</span>
			<div className="flex flex-wrap gap-2">
				{resources.map((resource) => {
					const resourceId = getResourceId(resource);
					const resourceName = getResourceName(resource);
					const displayText = resourceName || resourceId;

					return (
						<div key={resourceId} className="text-sm text-muted-foreground">
							{onResourceClick ? (
								<button
									type="button"
									onClick={() => onResourceClick(resourceId)}
									className="hover:underline"
								>
									{displayText}
								</button>
							) : (
								<span>{displayText}</span>
							)}
						</div>
					);
				})}
				{tags.length > 0 && (
					<div className="flex flex-wrap gap-1">
						{tags.map((tag) => {
							const tagId = getResourceId(tag);
							const tagName = getResourceName(tag) || tagId.split(".").pop();
							return (
								<Badge key={tagId} variant="secondary">
									{tagName}
								</Badge>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}

function EventTimelineItem({
	event,
	onEventClick,
	onResourceClick,
	onFilterEventsSince,
	onFilterEventsUntil,
}: EventTimelineItemProps) {
	const [isOpen, setIsOpen] = useState(false);
	const eventDate = new Date(event.occurred);

	return (
		<Collapsible open={isOpen} onOpenChange={setIsOpen}>
			<Card className="py-4">
				<CardHeader className="py-0">
					<div className="flex items-start justify-between gap-4">
						<div className="flex flex-col gap-3 flex-1 min-w-0">
							<div className="flex items-start justify-between gap-4">
								<EventNameWithPrefixes
									eventName={event.event}
									onEventClick={onEventClick}
								/>
								<div className="flex flex-col items-end gap-1">
									<EventTimestamp occurred={event.occurred} />
									{(onFilterEventsSince || onFilterEventsUntil) && (
										<div className="flex gap-1">
											{onFilterEventsSince && (
												<Button
													variant="ghost"
													size="sm"
													className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
													onClick={() => onFilterEventsSince(eventDate)}
												>
													Since
												</Button>
											)}
											{onFilterEventsUntil && (
												<Button
													variant="ghost"
													size="sm"
													className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
													onClick={() => onFilterEventsUntil(eventDate)}
												>
													Until
												</Button>
											)}
										</div>
									)}
								</div>
							</div>
							<EventResourceDisplay event={event} />
							{event.related && event.related.length > 0 && (
								<EventRelatedResources
									related={event.related}
									onResourceClick={onResourceClick}
								/>
							)}
						</div>
					</div>
				</CardHeader>
				<div className="px-6 pt-2">
					<CollapsibleTrigger asChild>
						<Button
							variant="ghost"
							size="sm"
							className="w-full justify-center gap-2 text-muted-foreground"
							aria-label={
								isOpen ? "Collapse event details" : "Expand event details"
							}
						>
							<ChevronDown
								className={cn(
									"h-4 w-4 transition-transform duration-200",
									isOpen && "rotate-180",
								)}
							/>
							<span className="text-xs">
								{isOpen ? "Hide raw event" : "Show raw event"}
							</span>
						</Button>
					</CollapsibleTrigger>
				</div>
				<CollapsibleContent>
					<CardContent className="pt-4">
						<JsonView
							value={JSON.stringify(event, null, 2)}
							className="max-h-96 overflow-auto"
						/>
					</CardContent>
				</CollapsibleContent>
			</Card>
		</Collapsible>
	);
}

export function EventsTimeline({
	events,
	onEventClick,
	onResourceClick,
	onFilterEventsSince,
	onFilterEventsUntil,
	className,
}: EventsTimelineProps) {
	if (!events || events.length === 0) {
		return null;
	}

	return (
		<div className={cn("flex flex-col gap-4", className)}>
			{events.map((event) => (
				<EventTimelineItem
					key={event.id}
					event={event}
					onEventClick={onEventClick}
					onResourceClick={onResourceClick}
					onFilterEventsSince={onFilterEventsSince}
					onFilterEventsUntil={onFilterEventsUntil}
				/>
			))}
		</div>
	);
}
