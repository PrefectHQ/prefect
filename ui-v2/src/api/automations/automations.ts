import {
	queryOptions,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getApiUrl, getQueryService } from "@/api/service";

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
			const res = await (await getQueryService()).POST("/automations/filter", {
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
			const res = await (await getQueryService()).GET("/automations/{id}", {
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
			const res = await (await getQueryService()).GET(
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
		mutationFn: async (id: string) =>
			(await getQueryService()).DELETE("/automations/{id}", {
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
		mutationFn: async (body: components["schemas"]["AutomationCreate"]) =>
			(await getQueryService()).POST("/automations/", { body }),
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
		mutationFn: async ({
			id,
			...body
		}: components["schemas"]["AutomationPartialUpdate"] & { id: string }) =>
			(await getQueryService()).PATCH("/automations/{id}", {
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

/**
 * Hook for fully replacing an automation by ID (PUT request)
 *
 * Use this hook when you need to update all fields of an automation (name, description, trigger, actions, etc.)
 * For partial updates (like toggling enabled), use useUpdateAutomation instead.
 *
 * @returns Mutation object for replacing an automation with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { replaceAutomation, isPending } = useReplaceAutomation();
 *
 * replaceAutomation({
 *   id: 'automation-id',
 *   name: 'Updated Name',
 *   description: 'Updated description',
 *   enabled: true,
 *   trigger: { ... },
 *   actions: [ ... ],
 * }, {
 *   onSuccess: () => {
 *     console.log('Automation replaced successfully');
 *   },
 *   onError: (error) => {
 *     console.error('Failed to replace automation', error);
 *   }
 * });
 * ```
 */
export const useReplaceAutomation = () => {
	const queryClient = useQueryClient();
	const { mutate: replaceAutomation, ...rest } = useMutation({
		mutationFn: async ({
			id,
			...body
		}: components["schemas"]["AutomationUpdate"] & { id: string }) =>
			(await getQueryService()).PUT("/automations/{id}", {
				body,
				params: { path: { id } },
			}),
		onSuccess: () => {
			// After a successful replacement, invalidate all to get an updated list and details
			return queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			});
		},
	});
	return {
		replaceAutomation,
		...rest,
	};
};

export type TemplateValidationError = {
	error: {
		line: number;
		message: string;
		source: string;
	};
};

/**
 * Hook for validating Jinja templates used in automation notifications
 *
 * @returns Mutation object for validating a template with loading/error states and trigger function
 *
 * @example
 * ```ts
 * const { validateTemplate, isPending } = useValidateTemplate();
 *
 * validateTemplate('Hello {{ flow.name }}', {
 *   onSuccess: () => {
 *     console.log('Template is valid');
 *   },
 *   onError: (error) => {
 *     console.error('Template validation failed:', error);
 *   }
 * });
 * ```
 */
export const useValidateTemplate = () => {
	const { mutateAsync: validateTemplate, ...rest } = useMutation({
		mutationFn: async (
			template: string,
		): Promise<{ valid: true } | { valid: false; error: string }> => {
			// Use raw fetch to avoid the error-throwing middleware in getQueryService()
			// since we want to handle 422 responses gracefully as validation errors
			const baseUrl = await getApiUrl();
			const response = await fetch(
				`${baseUrl}/automations/templates/validate`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify(template),
				},
			);

			if (response.ok) {
				return { valid: true };
			}

			try {
				const errorData =
					(await response.json()) as TemplateValidationError | null;
				if (errorData?.error) {
					return {
						valid: false,
						error: `Error on line ${errorData.error.line}: ${errorData.error.message}`,
					};
				}
			} catch {
				// JSON parsing failed, return generic error
			}
			return { valid: false, error: "Template validation failed" };
		},
	});
	return {
		validateTemplate,
		...rest,
	};
};
