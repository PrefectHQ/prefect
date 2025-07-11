import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";

export type Automation = components["schemas"]["Automation"];
export type AutomationsFilter =
	components["schemas"]["Body_read_automations_automations_filter_post"];

/**
 * ```
 *  🏗️ Automations queries construction 👷
 *  all   =>   	['automations'] // key to match ['automations', ...
 *  list  =>   	['automations', 'list'] // key to match ['automations, 'list', ...
 *  filters => 	['automations', 'list', 'filter'] // key to match ['automations, 'list', 'filters'...
 *             	['automations', 'list', 'filter', { ...filter2 }]
 *             	['automations', 'list', 'filter', { ...filter2 }]
 * 	relates =>	['automations', 'list', 'relates'] // keys to match 'list', 'relates'
 *				['automations', 'list', 'relates', relatedResourceId]
 *  details => 	['automations', 'details'] // key to match ['automations', 'details', ...
 *             	['automations', 'details', id1]
 *             	['automations', 'details', id2]
 * ```
 * */
export const queryKeyFactory = {
	all: () => ["automations"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	filters: () => [...queryKeyFactory.lists(), "filter"] as const,
	filter: (filter: AutomationsFilter) =>
		[...queryKeyFactory.filters(), filter] as const,
	relates: () => [...queryKeyFactory.lists(), "relates"] as const,
	relate: (resourceId: string) =>
		[...queryKeyFactory.relates(), resourceId] as const,
	details: () => [...queryKeyFactory.all(), "details"] as const,
	detail: (id: string) => [...queryKeyFactory.details(), id] as const,
};

// ----- 🔑 Queries 🗄️
// ----------------------------
export const buildListAutomationsQuery = (
	filter: AutomationsFilter = { sort: "CREATED_DESC", offset: 0 },
) =>
	queryOptions({
		queryKey: queryKeyFactory.filter(filter),
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

// nb: update resource_id string template
type PrefectResources = "prefect.deployment.";
export const buildListAutomationsRelatedQuery = (
	resource_id: `${PrefectResources}${string}`,
) =>
	queryOptions({
		queryKey: queryKeyFactory.relate(resource_id),
		queryFn: async () => {
			const res = await getQueryService().GET(
				"/automations/related-to/{resource_id}",
				{ params: { path: { resource_id } } },
			);
			return res.data ?? [];
		},
	});

// ----- ✍🏼 Mutations 🗄️
// ----------------------------

/**
 * Hook for deleting an automation
 *
 * @returns Mutation object for deleting an automation with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { deleteAutomation } = useDeleteAutomation();
 *
 * // Delete an automation by id
 * deleteAutomation('id-to-delete', {
 *   onSuccess: () => {
 *     // Handle successful deletion
 *   },
 *   onError: (error) => {
 *     console.error('Failed to delete automation:', error);
 *   }
 * });
 * ```
 */
export const useDeleteAutomation = () => {
	const queryClient = useQueryClient();
	const { mutate: deleteAutomation, ...rest } = useMutation({
		mutationFn: (id: string) =>
			getQueryService().DELETE("/automations/{id}", {
				params: { path: { id } },
			}),
		onSuccess: () => {
			// After a successful deletion, invalidate the listing queries only to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		deleteAutomation,
		...rest,
	};
};

/**
 * Hook for creating a new automation
 *
 * @returns Mutation object for creating an automation with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { createAutomation, isLoading } = useCreateAutomation();
 *
 * createAutomation(newAutomation, {
 *   onSuccess: () => {
 *     // Handle successful creation
 *     console.log('Automation created successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to create automation:', error);
 *   }
 * });
 * ```
 */
export const useCreateAutomation = () => {
	const queryClient = useQueryClient();
	const { mutate: createAutomation, ...rest } = useMutation({
		mutationFn: (body: components["schemas"]["AutomationCreate"]) =>
			getQueryService().POST("/automations/", { body }),
		onSuccess: () => {
			// After a successful creation, invalidate the listing queries only to refetch
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.lists(),
			});
		},
	});
	return {
		createAutomation,
		...rest,
	};
};

/**
 * Hook for editing an automation based on ID
 *
 * @returns Mutation object for editing an automation with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { updateAutomation, isLoading } = useUpdateAutomation();
 *
 * // Create a new task run concurrency limit
 * updateAutomation('my-id', {
 *   onSuccess: () => {
 *     console.log('Automation edited successfully');
 *   },
 *   onError: (error) => {
 *     // Handle error
 *     console.error('Failed to edit automation', error);
 *   }
 * });
 * ```
 */
export const useUpdateAutomation = () => {
	const queryClient = useQueryClient();
	const { mutate: updateAutomation, ...rest } = useMutation({
		mutationFn: ({
			id,
			...body
		}: components["schemas"]["AutomationPartialUpdate"] & { id: string }) =>
			getQueryService().PATCH("/automations/{id}", {
				body,
				params: { path: { id } },
			}),
		onSuccess: () => {
			// After a successful reset, invalidate all to get an updated list and details list
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});
	return {
		updateAutomation,
		...rest,
	};
};
