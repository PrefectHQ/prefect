import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";

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
