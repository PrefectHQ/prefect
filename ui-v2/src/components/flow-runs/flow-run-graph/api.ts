import type {
	EventRelatedResource,
	RunGraphArtifact,
	RunGraphData,
	RunGraphEvent,
	RunGraphEventResource,
	RunGraphFetchEventsContext,
	RunGraphNode,
} from "@prefecthq/graphs";
import { parseISO } from "date-fns";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

/**
 * Fetches the graph data for a flow run.
 * @param id - The ID of the flow run.
 * @returns The graph data for the flow run.
 */
export async function fetchFlowRunGraph(id: string): Promise<RunGraphData> {
	const { data } = await getQueryService().GET("/flow_runs/{id}/graph-v2", {
		params: { path: { id } },
	});

	if (!data) {
		throw new Error("No data returned from API");
	}

	return mapApiResponseToRunGraphData(data);
}

/**
 * Fetches events for a flow run.
 * @param since - The start date of the events to fetch.
 * @param until - The end date of the events to fetch.
 * @param nodeId - The flowRunId of the node to fetch events for.
 * @returns The events for the flow run.
 */
export async function fetchFlowRunEvents({
	since,
	until,
	nodeId,
}: RunGraphFetchEventsContext): Promise<RunGraphEvent[]> {
	const { data } = await getQueryService().POST("/events/filter", {
		body: {
			filter: {
				any_resource: {
					id: [`prefect.flow-run.${nodeId}`],
				},
				event: {
					exclude_prefix: ["prefect.log.write", "prefect.task-run."],
				},
				occurred: {
					since: since.toISOString(),
					until: until.toISOString(),
				},
				order: "ASC",
			},
			limit: 200,
		},
	});

	if (!data) {
		throw new Error("No data returned from API");
	}

	return mapApiResponseToRunGraphEvents(data);
}

type GraphResponse = components["schemas"]["Graph"];
type GraphResponseNode = GraphResponse["nodes"][number];
type GraphResponseArtifact = GraphResponse["artifacts"][number];
type EventsResponse = components["schemas"]["EventPage"];

function mapApiResponseToRunGraphData(response: GraphResponse): RunGraphData {
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
