import { components } from "@/api/prefect";
import { RunGraphArtifact, RunGraphData, RunGraphNode } from "@prefecthq/graphs";
import { parseISO } from "date-fns";

type ApiResponse = components["schemas"]["Graph"]
type ApiResponseNode = ApiResponse["nodes"][number]
type ApiResponseArtifact = ApiResponse["artifacts"][number]

export function mapApiResponseToRunGraphData(response: ApiResponse): RunGraphData {
  if(!response.start_time) {
    throw new Error("Start time is required")
  }

  return {
    root_node_ids: response.root_node_ids,
    start_time: parseISO(response.start_time),
    end_time: response.end_time ? parseISO(response.end_time) : null,
    nodes: new Map(response.nodes.map((node => mapNode(node)))),
  }
}

function mapNode([id, node]: ApiResponseNode): [string, RunGraphNode] {
  if(!node.start_time) {
    throw new Error("Start time is required")
  }

  return [id, {
    kind: node.kind,
    id: node.id,
    label: node.label,
    state_type: node.state_type,
    start_time: parseISO(node.start_time),
    end_time: node.end_time ? parseISO(node.end_time) : null,
    parents: node.parents,
    children: node.children,
    artifacts: node.artifacts.map(mapArtifact),
  }]
}

function mapArtifact(artifact: ApiResponseArtifact): RunGraphArtifact {
  if(!artifact.type) {
    throw new Error("Artifact type is required")
  }

  if(artifact.type === 'progress' && typeof artifact.data === 'number') {
    return {
      id: artifact.id,
      created: parseISO(artifact.created),
      key: artifact.key ?? undefined,
      type: artifact.type,
      data: artifact.data,
    }
  }

  return {
    id: artifact.id,
    created: parseISO(artifact.created),
    key: artifact.key ?? undefined,
    type: artifact.type as RunGraphArtifact["type"],
  }
}