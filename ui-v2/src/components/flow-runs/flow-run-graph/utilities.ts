import { components } from "@/api/prefect";
import {
	EventRelatedResource,
	RunGraphArtifact,
	RunGraphData,
	RunGraphEvent,
	RunGraphEventResource,
	RunGraphNode,
} from "@prefecthq/graphs";
import { parseISO } from "date-fns";

export function isEventTargetInput(target: EventTarget | null): boolean {
	if (!target || !(target instanceof HTMLElement)) {
		return false;
	}
	return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

type GraphResponse = components["schemas"]["Graph"];
type GraphResponseNode = GraphResponse["nodes"][number];
type GraphResponseArtifact = GraphResponse["artifacts"][number];
type EventsResponse = components["schemas"]["EventPage"];

export function mapApiResponseToRunGraphData(
	response: GraphResponse,
): RunGraphData {
	if (!response.start_time) {
		throw new Error("Start time is required");
	}

	return {
		root_node_ids: response.root_node_ids,
		start_time: parseISO(response.start_time),
		end_time: response.end_time ? parseISO(response.end_time) : null,
		nodes: new Map(response.nodes.map((node) => mapNode(node))),
	};
}

export function mapApiResponseToRunGraphEvents(
	response: EventsResponse,
): RunGraphEvent[] {
	return response.events.map((event) => {
		if (!event.received) {
			throw new Error("Received is required");
		}

		const runGraphEvent: RunGraphEvent = {
			id: event.id,
			received: parseISO(event.received),
			occurred: parseISO(event.occurred),
			event: event.event,
			resource: event.resource as RunGraphEventResource,
			payload: event.payload,
			related: (event.related ?? []) as EventRelatedResource[],
		};

		return runGraphEvent;
	});
}

function mapNode([id, node]: GraphResponseNode): [string, RunGraphNode] {
	if (!node.start_time) {
		throw new Error("Start time is required");
	}

	return [
		id,
		{
			kind: node.kind,
			id: node.id,
			label: node.label,
			state_type: node.state_type,
			start_time: parseISO(node.start_time),
			end_time: node.end_time ? parseISO(node.end_time) : null,
			parents: node.parents,
			children: node.children,
			artifacts: node.artifacts.map(mapArtifact),
		},
	];
}

function mapArtifact(artifact: GraphResponseArtifact): RunGraphArtifact {
	if (!artifact.type) {
		throw new Error("Artifact type is required");
	}

	if (artifact.type === "progress" && typeof artifact.data === "number") {
		return {
			id: artifact.id,
			created: parseISO(artifact.created),
			key: artifact.key ?? undefined,
			type: artifact.type,
			data: artifact.data,
		};
	}

	return {
		id: artifact.id,
		created: parseISO(artifact.created),
		key: artifact.key ?? undefined,
		type: artifact.type as Exclude<RunGraphArtifact["type"], "progress">,
	};
}
