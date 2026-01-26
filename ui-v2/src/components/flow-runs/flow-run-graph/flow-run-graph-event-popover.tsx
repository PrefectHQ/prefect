import type { EventSelection } from "@prefecthq/graphs";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { format, isValid, parseISO } from "date-fns";
import { Suspense } from "react";
import { buildGetEventQuery, type Event } from "@/api/events";
import type { components } from "@/api/prefect";
import {
	EventResourceLink,
	extractResourceId,
	parseResourceType,
	ResourceDisplaySkeleton,
	ResourceDisplayWithIcon,
} from "@/components/events/event-resource-display";
import { ResolvedResourceDisplay } from "@/components/events/event-resource-display/resolved-resource-display";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { KeyValue } from "@/components/ui/key-value";
import {
	Popover,
	PopoverAnchor,
	PopoverContent,
} from "@/components/ui/popover";

type RelatedResource = components["schemas"]["RelatedResource"];

type FlowRunGraphEventPopoverProps = {
	selection: EventSelection;
	onClose: () => void;
};

/**
 * Converts an event name like "prefect.flow-run.Running" to a human-readable label
 * like "Flow run running"
 */
function getEventLabel(eventName: string): string {
	// Remove "prefect." or "prefect-cloud." prefix
	let label = eventName;
	if (label.startsWith("prefect.")) {
		label = label.slice(8);
	} else if (label.startsWith("prefect-cloud.")) {
		label = label.slice(14);
	}

	// Replace dots, dashes, and underscores with spaces
	label = label.replace(/[._-]/g, " ");

	// Capitalize first letter, lowercase the rest
	return label.charAt(0).toUpperCase() + label.slice(1).toLowerCase();
}

/**
 * Formats a date to numeric format like "2026/01/25 08:18:11 PM"
 */
function formatDateNumeric(date: string | Date): string {
	let parsedDate: Date;
	if (typeof date === "string") {
		parsedDate = parseISO(date);
	} else {
		parsedDate = date;
	}

	if (!isValid(parsedDate)) {
		return "Invalid date";
	}

	return format(parsedDate, "yyyy/MM/dd hh:mm:ss a");
}

function getResourceName(resource: Record<string, string>): string | null {
	return (
		resource["prefect.resource.name"] ||
		resource["prefect.name"] ||
		resource["prefect-cloud.name"] ||
		null
	);
}

type EventResourceSectionProps = {
	event: Event;
};

function EventResourceSection({ event }: EventResourceSectionProps) {
	const resourceName = getResourceName(event.resource);
	const prefectResourceId = event.resource["prefect.resource.id"] || "";
	const resourceType = parseResourceType(prefectResourceId);
	const extractedId = extractResourceId(prefectResourceId);
	const relatedResources = event.related ?? [];

	// If we have a resource name, display it with the appropriate icon
	if (resourceName) {
		return (
			<Suspense fallback={<ResourceDisplaySkeleton />}>
				<EventResourceLink
					resource={event.resource as RelatedResource}
					relatedResources={relatedResources}
					className="hover:underline text-primary"
				>
					<ResourceDisplayWithIcon
						resourceType={resourceType}
						displayText={resourceName}
						className="text-sm"
					/>
				</EventResourceLink>
			</Suspense>
		);
	}

	// If we have an extracted ID but no name, try to fetch the resource name via API
	if (extractedId && resourceType !== "unknown") {
		return (
			<Suspense fallback={<ResourceDisplaySkeleton />}>
				<EventResourceLink
					resource={event.resource as RelatedResource}
					relatedResources={relatedResources}
					className="hover:underline text-primary"
				>
					<ResolvedResourceDisplay
						resourceType={resourceType}
						resourceId={extractedId}
						className="text-sm"
					/>
				</EventResourceLink>
			</Suspense>
		);
	}

	// Fallback: show the raw resource ID
	return (
		<span className="text-sm text-muted-foreground font-mono">
			{prefectResourceId || "Unknown"}
		</span>
	);
}

type RelatedResourcesSectionProps = {
	relatedResources: RelatedResource[];
};

function RelatedResourcesSection({
	relatedResources,
}: RelatedResourcesSectionProps) {
	// Filter out tag resources and only show meaningful related resources
	const filteredResources = relatedResources.filter((resource) => {
		const role = resource["prefect.resource.role"];
		const resourceId = resource["prefect.resource.id"] || "";
		// Exclude tags and resources without a valid type
		if (role === "tag" || resourceId.startsWith("prefect.tag.")) {
			return false;
		}
		const resourceType = parseResourceType(resourceId);
		return resourceType !== "unknown";
	});

	if (filteredResources.length === 0) {
		return null;
	}

	return (
		<KeyValue
			label="Related Resources"
			value={
				<div className="flex flex-col gap-1">
					{filteredResources.map((resource) => {
						const resourceName = getResourceName(resource);
						const prefectResourceId = resource["prefect.resource.id"] || "";
						const resourceType = parseResourceType(prefectResourceId);
						const extractedId = extractResourceId(prefectResourceId);

						if (resourceName) {
							return (
								<Suspense
									key={prefectResourceId}
									fallback={<ResourceDisplaySkeleton />}
								>
									<EventResourceLink
										resource={resource}
										relatedResources={relatedResources}
										className="hover:underline text-primary"
									>
										<ResourceDisplayWithIcon
											resourceType={resourceType}
											displayText={resourceName}
											className="text-sm"
										/>
									</EventResourceLink>
								</Suspense>
							);
						}

						if (extractedId && resourceType !== "unknown") {
							return (
								<Suspense
									key={prefectResourceId}
									fallback={<ResourceDisplaySkeleton />}
								>
									<EventResourceLink
										resource={resource}
										relatedResources={relatedResources}
										className="hover:underline text-primary"
									>
										<ResolvedResourceDisplay
											resourceType={resourceType}
											resourceId={extractedId}
											className="text-sm"
										/>
									</EventResourceLink>
								</Suspense>
							);
						}

						return (
							<span
								key={prefectResourceId}
								className="text-sm text-muted-foreground font-mono"
							>
								{prefectResourceId}
							</span>
						);
					})}
				</div>
			}
		/>
	);
}

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

	const eventName = event?.event ?? "";
	const eventLabel = eventName ? getEventLabel(eventName) : "Loading...";
	const relatedResources = event?.related ?? [];

	return (
		<Popover open onOpenChange={(open) => !open && onClose()}>
			<PopoverAnchor style={anchorStyle} />
			<PopoverContent align="center" side="bottom" className="w-80">
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
							value={
								<div className="flex flex-col gap-0.5">
									<Link
										to="/events"
										search={{ event: [eventName] }}
										className="text-sm text-primary hover:underline font-medium"
									>
										{eventLabel}
									</Link>
									<span className="text-xs text-muted-foreground">
										{eventName}
									</span>
								</div>
							}
						/>
						<KeyValue
							label="Occurred"
							value={
								<span className="text-sm">
									{formatDateNumeric(selection.occurred)}
								</span>
							}
						/>
						{event && (
							<KeyValue
								label="Resource"
								value={<EventResourceSection event={event} />}
							/>
						)}
						{relatedResources.length > 0 && (
							<RelatedResourcesSection relatedResources={relatedResources} />
						)}
					</div>
				)}
			</PopoverContent>
		</Popover>
	);
}
