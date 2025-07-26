import { queryOptions } from "@tanstack/react-query";
import { getQueryService } from "@/api/service";

// Define WorkPoolWorker interface since it's not in the generated types yet
export interface WorkPoolWorker {
	id: string;
	created: string;
	updated: string;
	name: string;
	work_pool_id: string;
	last_heartbeat_time: string | null;
	status: "online" | "offline";
}

// API response interface
interface ApiWorkerResponse {
	id: string;
	created: string | null;
	updated: string | null;
	name: string;
	work_pool_id: string;
	last_heartbeat_time?: string | null;
	status: "ONLINE" | "OFFLINE";
}

/**
 * Query key factory for work pool workers-related queries
 *
 * @property {function} all - Returns base key for all work pool worker queries
 * @property {function} lists - Returns key for all list-type work pool worker queries
 * @property {function} list - Generates key for specific work pool worker queries
 *
 * ```
 * all		=>   ['work_pool_workers']
 * lists	=>   ['work_pool_workers', 'list']
 * list		=>   ['work_pool_workers', 'list', workPoolName]
 * ```
 */
export const workPoolWorkersQueryKeyFactory = {
	all: () => ["work_pool_workers"] as const,
	lists: () => [...workPoolWorkersQueryKeyFactory.all(), "list"] as const,
	list: (workPoolName: string) =>
		[...workPoolWorkersQueryKeyFactory.lists(), workPoolName] as const,
} as const;

/**
 * Builds a query configuration for fetching work pool workers
 *
 * @param workPoolName - Name of the work pool to fetch workers for
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const query = useQuery(buildListWorkPoolWorkersQuery('my-work-pool'));
 * ```
 */
export const buildListWorkPoolWorkersQuery = (workPoolName: string) =>
	queryOptions({
		queryKey: workPoolWorkersQueryKeyFactory.list(workPoolName),
		queryFn: async (): Promise<WorkPoolWorker[]> => {
			const res = await getQueryService().POST(
				"/work_pools/{work_pool_name}/workers/filter",
				{
					params: { path: { work_pool_name: workPoolName } },
					body: {
						offset: 0,
					},
				},
			);
			if (!res.data) {
				throw new Error("'data' expected");
			}
			// Transform API response to match our interface
			return res.data.map(
				(worker: ApiWorkerResponse): WorkPoolWorker => ({
					id: worker.id,
					created: worker.created || new Date().toISOString(),
					updated: worker.updated || new Date().toISOString(),
					name: worker.name,
					work_pool_id: worker.work_pool_id,
					last_heartbeat_time: worker.last_heartbeat_time || null,
					status:
						worker.status?.toLowerCase() === "online" ? "online" : "offline",
				}),
			);
		},
		refetchInterval: 30000, // 30 seconds for real-time updates
	});
