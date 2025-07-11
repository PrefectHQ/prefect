import { queryOptions } from "@tanstack/react-query";
import { getQueryService } from "@/api/service";

/**
 * ```
 *  🏗️ Admin queries construction 👷
 *  settings   =>   ['settings'] // key to match ['settings']
 *  version   =>   ['version'] // key to match ['version']
 * ```
 * */
export const queryKeyFactory = {
	settings: () => ["settings"] as const,
	version: () => ["version"] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------

/**
 *
 * @returns react query options object for getting the Prefect's version number
 */
export const buildGetVersionQuery = () =>
	queryOptions({
		queryKey: queryKeyFactory.version(),
		queryFn: async () => {
			const res = await getQueryService().GET("/admin/version");
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});

/**
 *
 * @returns react query options object for getting the Prefect server's settings information
 */
export const buildGetSettingsQuery = () =>
	queryOptions({
		queryKey: queryKeyFactory.settings(),
		queryFn: async () => {
			const res = await getQueryService().GET("/admin/settings");
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
