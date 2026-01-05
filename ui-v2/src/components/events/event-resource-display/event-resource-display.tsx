import { Suspense } from "react";
import type { Event } from "@/api/events";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils";
import { EventResourceLink } from "./event-resource-link";
import { ResolvedResourceDisplay } from "./resolved-resource-display";
import {
	extractResourceId,
	parseResourceType,
	RESOURCE_ICONS,
	RESOURCE_TYPE_LABELS,
	type ResourceType,
} from "./resource-types";

export type EventResourceDisplayProps = {
	event: Event;
	className?: string;
};

function getResourceName(resource: Record<string, string>): string | null {
	return (
		resource["prefect.resource.name"] ||
		resource["prefect.name"] ||
		resource["prefect-cloud.name"] ||
		null
	);
}

function getResourceId(resource: Record<string, string>): string {
	return resource["prefect.resource.id"] || "";
}

type ResourceDisplayWithIconProps = {
	resourceType: ResourceType;
	displayText: string;
	className?: string;
};

export function ResourceDisplayWithIcon({
	resourceType,
	displayText,
	className,
}: ResourceDisplayWithIconProps) {
	const iconId = RESOURCE_ICONS[resourceType];
	const typeLabel = RESOURCE_TYPE_LABELS[resourceType];

	return (
		<div className={cn("flex items-center gap-2", className)}>
			{typeLabel && <span>{typeLabel}</span>}
			<Icon id={iconId} className="h-4 w-4 text-muted-foreground" />
			<span>{displayText}</span>
		</div>
	);
}

export function ResourceDisplaySkeleton() {
	return (
		<div className="flex items-center gap-2">
			<Skeleton className="h-4 w-4 rounded-full" />
			<Skeleton className="h-4 w-24" />
		</div>
	);
}

export function EventResourceDisplay({
	event,
	className,
}: EventResourceDisplayProps) {
	const resourceName = getResourceName(event.resource);
	const prefectResourceId = getResourceId(event.resource);
	const resourceType = parseResourceType(prefectResourceId);
	const extractedId = extractResourceId(prefectResourceId);

	// If we have a resource name, display it with the appropriate icon
	if (resourceName) {
		return (
			<div className={cn("flex flex-col gap-0.5", className)}>
				<span className="text-sm font-medium">Resource</span>
				<Suspense fallback={<ResourceDisplaySkeleton />}>
					<EventResourceLink
						resource={event.resource}
						relatedResources={event.related ?? []}
						className="hover:underline"
					>
						<ResourceDisplayWithIcon
							resourceType={resourceType}
							displayText={resourceName}
							className="text-sm"
						/>
					</EventResourceLink>
				</Suspense>
			</div>
		);
	}

	// If we have an extracted ID but no name, try to fetch the resource name via API
	if (extractedId && resourceType !== "unknown") {
		return (
			<div className={cn("flex flex-col gap-0.5", className)}>
				<span className="text-sm font-medium">Resource</span>
				<Suspense fallback={<ResourceDisplaySkeleton />}>
					<EventResourceLink
						resource={event.resource}
						relatedResources={event.related ?? []}
						className="hover:underline"
					>
						<ResolvedResourceDisplay
							resourceType={resourceType}
							resourceId={extractedId}
							className="text-sm"
						/>
					</EventResourceLink>
				</Suspense>
			</div>
		);
	}

	// If we have an extracted ID but unknown type, show the ID with the icon
	if (extractedId) {
		return (
			<div className={cn("flex flex-col gap-0.5", className)}>
				<span className="text-sm font-medium">Resource</span>
				<Suspense fallback={<ResourceDisplaySkeleton />}>
					<EventResourceLink
						resource={event.resource}
						relatedResources={event.related ?? []}
						className="hover:underline"
					>
						<ResourceDisplayWithIcon
							resourceType={resourceType}
							displayText={extractedId}
							className="text-sm text-muted-foreground font-mono"
						/>
					</EventResourceLink>
				</Suspense>
			</div>
		);
	}

	// Fallback: show the raw resource ID if nothing else is available
	if (prefectResourceId) {
		return (
			<div className={cn("flex flex-col gap-0.5", className)}>
				<span className="text-sm font-medium">Resource</span>
				<EventResourceLink
					resource={event.resource}
					relatedResources={event.related ?? []}
					className="hover:underline"
				>
					<div className="text-sm text-muted-foreground">
						<span className="font-mono text-xs">{prefectResourceId}</span>
					</div>
				</EventResourceLink>
			</div>
		);
	}

	// No resource information available
	return (
		<div className={cn("flex flex-col gap-0.5", className)}>
			<span className="text-sm font-medium">Resource</span>
			<div className="text-sm text-muted-foreground">
				<span className="text-muted-foreground">Unknown</span>
			</div>
		</div>
	);
}
