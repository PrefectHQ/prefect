import { Link } from "@tanstack/react-router";
import { format } from "date-fns";
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
import { Icon } from "@/components/ui/icons";
import { JsonView } from "@/components/ui/json-view";
import { cn } from "@/utils";
import {
	EventResourceDisplay,
	EventResourceLink,
} from "../event-resource-display";
import {
	parseResourceType,
	RESOURCE_ICONS,
	RESOURCE_TYPE_LABELS,
} from "../event-resource-display/resource-types";
import { formatEventLabel } from "./utilities";

type Event = components["schemas"]["ReceivedEvent"];

type EventsTimelineProps = {
	events: Event[];
	className?: string;
};

type EventTimelineItemProps = {
	event: Event;
	isLast: boolean;
};

function EventTimestamp({ occurred }: { occurred: string }) {
	const date = new Date(occurred);
	const formattedTime = format(date, "h:mm:ss a");
	const formattedDate = format(date, "MMM do, yyyy");

	return (
		<div className="flex flex-col text-right text-sm w-24 shrink-0">
			<span>{formattedTime}</span>
			<span className="text-xs text-muted-foreground">{formattedDate}</span>
		</div>
	);
}

function TimelinePoint({ event, isLast }: { event: Event; isLast: boolean }) {
	const resourceId = event.resource["prefect.resource.id"] || "";
	const resourceType = parseResourceType(resourceId);
	const iconId = RESOURCE_ICONS[resourceType];

	return (
		<div className="relative flex items-start justify-center w-10 h-full">
			{/* Vertical line - extends from top to bottom, hidden for last item below the icon */}
			<div
				className={cn(
					"absolute left-1/2 w-px -translate-x-1/2 bg-border",
					isLast ? "top-0 h-5" : "top-0 bottom-0",
				)}
				style={{ top: "-1rem", bottom: isLast ? "auto" : "-1rem" }}
			/>
			{/* Icon circle */}
			<div className="relative flex items-center justify-center w-10 h-10 rounded-full bg-background border border-border">
				<Icon id={iconId} className="h-5 w-5 text-muted-foreground" />
			</div>
		</div>
	);
}

/**
 * Formats a Date object as YYYY-MM-DD for use in route parameters.
 */
function formatRouteDate(date: Date): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, "0");
	const day = String(date.getDate()).padStart(2, "0");
	return `${year}-${month}-${day}`;
}

function EventNameWithPrefixes({
	eventId,
	eventName,
	occurred,
}: {
	eventId: string;
	eventName: string;
	occurred: string;
}) {
	const label = formatEventLabel(eventName);
	const eventDate = formatRouteDate(new Date(occurred));

	return (
		<div className="flex flex-col gap-0.5">
			<Link
				to="/events/event/$eventDate/$eventId"
				params={{ eventDate, eventId }}
				className="text-left font-medium hover:underline"
			>
				{label}
			</Link>
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
}: {
	related: components["schemas"]["RelatedResource"][];
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
					const resourceType = parseResourceType(resourceId);
					const typeLabel = RESOURCE_TYPE_LABELS[resourceType];
					const iconId = RESOURCE_ICONS[resourceType];

					return (
						<EventResourceLink
							key={resourceId}
							resource={resource}
							relatedResources={related}
							className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground hover:underline"
						>
							{typeLabel && <span>{typeLabel}</span>}
							<Icon id={iconId} className="h-4 w-4" />
							<span>{displayText}</span>
						</EventResourceLink>
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

function EventTimelineItem({ event, isLast }: EventTimelineItemProps) {
	const [isOpen, setIsOpen] = useState(false);

	return (
		<div className="grid grid-cols-[6rem_2.5rem_1fr] gap-4 items-start py-4">
			{/* Date column */}
			<EventTimestamp occurred={event.occurred} />

			{/* Point column with icon and vertical line */}
			<TimelinePoint event={event} isLast={isLast} />

			{/* Content column */}
			<Collapsible open={isOpen} onOpenChange={setIsOpen}>
				<Card className="py-4">
					<CardHeader className="py-0">
						<div className="flex flex-col gap-3">
							<EventNameWithPrefixes
								eventId={event.id}
								eventName={event.event}
								occurred={event.occurred}
							/>
							<EventResourceDisplay event={event} />
							{event.related && event.related.length > 0 && (
								<EventRelatedResources related={event.related} />
							)}
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
		</div>
	);
}

export function EventsTimeline({ events, className }: EventsTimelineProps) {
	if (!events || events.length === 0) {
		return null;
	}

	return (
		<ol className={cn("list-none p-0 m-0", className)}>
			{events.map((event, index) => (
				<li key={event.id}>
					<EventTimelineItem
						event={event}
						isLast={index === events.length - 1}
					/>
				</li>
			))}
		</ol>
	);
}
