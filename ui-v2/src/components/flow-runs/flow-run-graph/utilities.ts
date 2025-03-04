import { components } from "@/api/prefect";
import { RunGraphData } from "@prefecthq/graphs";

type ApiResponse = components["schemas"]["DependencyResult"][]

export function mapApiResponseToRunGraphData(response: ApiResponse): RunGraphData {
  return response
}