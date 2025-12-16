import type { components } from "@/api/prefect";
import { extractResourceId, parseResourceType } from "./resource-types";

type RelatedResource = components["schemas"]["RelatedResource"];

export type ResourceRouteConfig = {
	to: string;
	params: Record<string, string>;
};

function getResourceName(resource: RelatedResource): string | null {
	return (
		resource["prefect.resource.name"] ||
		resource["prefect.name"] ||
		resource["prefect-cloud.name"] ||
		null
	);
}

export function getResourceRoute(
	resource: RelatedResource,
): ResourceRouteConfig | null {
	const resourceId = resource["prefect.resource.id"] || "";
	const resourceType = parseResourceType(resourceId);
	const extractedId = extractResourceId(resourceId);

	if (!extractedId) {
		return null;
	}

	switch (resourceType) {
		case "flow-run":
			return {
				to: "/runs/flow-run/$id",
				params: { id: extractedId },
			};
		case "task-run":
			return {
				to: "/runs/task-run/$id",
				params: { id: extractedId },
			};
		case "deployment":
			return {
				to: "/deployments/deployment/$id",
				params: { id: extractedId },
			};
		case "flow":
			return {
				to: "/flows/flow/$id",
				params: { id: extractedId },
			};
		case "work-pool": {
			// Work pools use name instead of id in the route
			const workPoolName = getResourceName(resource) || extractedId;
			return {
				to: "/work-pools/work-pool/$workPoolName",
				params: { workPoolName },
			};
		}
		case "automation":
			return {
				to: "/automations/automation/$id",
				params: { id: extractedId },
			};
		case "block-document":
			return {
				to: "/blocks/block/$id",
				params: { id: extractedId },
			};
		case "concurrency-limit":
			return {
				to: "/concurrency-limits/concurrency-limit/$id",
				params: { id: extractedId },
			};
		case "work-queue":
			// Work queues require both work pool name and queue name
			// which we don't have from the resource alone, so skip linking
			return null;
		default:
			return null;
	}
}
