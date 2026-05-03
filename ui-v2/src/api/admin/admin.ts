import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

/**
 * ```
 *  🏗️ Admin queries construction 👷
 *  settings              =>   ['settings'] // key to match ['settings']
 *  version               =>   ['version'] // key to match ['version']
 *  defaultResultStorage  =>   ['default-result-storage'] // key to match ['default-result-storage']
 * ```
 * */
export const queryKeyFactory = {
	settings: () => ["settings"] as const,
	version: () => ["version"] as const,
	defaultResultStorage: () => ["default-result-storage"] as const,
};

export type ServerDefaultResultStorage =
	components["schemas"]["ServerDefaultResultStorage"];
export type ServerDefaultResultStorageUpdate =
	components["schemas"]["ServerDefaultResultStorageUpdate"];

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
			const res = await (await getQueryService()).GET("/admin/version");
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
			const res = await (await getQueryService()).GET("/admin/settings");
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});

/**
 *
 * @returns react query options object for getting the server default result storage block
 */
export const buildGetDefaultResultStorageQuery = () =>
	queryOptions({
		queryKey: queryKeyFactory.defaultResultStorage(),
		queryFn: async () => {
			const res = await (await getQueryService()).GET("/admin/storage");
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});

export const useUpdateDefaultResultStorage = () => {
	const queryClient = useQueryClient();

	const { mutate: updateDefaultResultStorage, ...rest } = useMutation({
		mutationFn: async (body: ServerDefaultResultStorageUpdate) =>
			(await getQueryService()).PUT("/admin/storage", { body }),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.defaultResultStorage(),
			}),
	});

	return { updateDefaultResultStorage, ...rest };
};

export const useClearDefaultResultStorage = () => {
	const queryClient = useQueryClient();

	const { mutate: clearDefaultResultStorage, ...rest } = useMutation({
		mutationFn: async () => (await getQueryService()).DELETE("/admin/storage"),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.defaultResultStorage(),
			}),
	});

	return { clearDefaultResultStorage, ...rest };
};
