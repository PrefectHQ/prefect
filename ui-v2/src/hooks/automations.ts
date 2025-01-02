import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { queryOptions } from "@tanstack/react-query";

export type Automation = components["schemas"]["Automation"];
export type AutomationsFilter =
	components["schemas"]["Body_read_automations_automations_filter_post"];

/**
 * ```
 *  🏗️ Automations queries construction 👷
 *  all   =>   ['automations'] // key to match ['automationss', ...
 *  list  =>   ['automations', 'list'] // key to match ['automations, 'list', ...
 *             ['automations', 'list', { ...filter1 }]
 *             ['automations', 'list', { ...filter2 }]
 *  details => ['automations', 'details'] // key to match ['automations', 'details', ...
 *             ['automations', 'details', id1]
 *             ['automations', 'details', id2]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["automations"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	list: (filter: AutomationsFilter) =>
		[...queryKeyFactory.lists(), filter] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListAutomationsQuery = (
	filter: AutomationsFilter = { sort: "CREATED_DESC", offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.list(filter),
		queryFn: async () => {
			const res = await getQueryService().POST("/automations/filter", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});

export const buildGetAutomationQuery = (id: string) =>
	queryOptions({
		queryKey: queryKeyFactory.detail(id),
		queryFn: async () => {
			const res = await getQueryService().GET("/automations/{id}", {
				params: { path: { id } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
	});
