import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getQueryService } from "@/api/service";
import { workPoolQueuesQueryKeyFactory } from "@/api/work-pool-queues";

type BulkUpdatePrioritiesParams = {
	workPoolName: string;
	updates: Array<{ id: string; priority: number }>;
};

export const useBulkUpdatePrioritiesMutation = () => {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: async ({ updates }: BulkUpdatePrioritiesParams) => {
			// Update priorities one by one using the existing PATCH API
			const results = [];
			for (const update of updates) {
				try {
					const response = await getQueryService().PATCH("/work_queues/{id}", {
						params: { path: { id: update.id } },
						body: {
							priority: update.priority,
							is_paused: false, // Required field - keep existing state
						},
					});
					results.push({ id: update.id, success: true, data: response.data });
				} catch (error) {
					results.push({ id: update.id, success: false, error });
				}
			}

			const failedUpdates = results.filter((r) => !r.success);
			if (failedUpdates.length > 0) {
				throw new Error(
					`Failed to update ${failedUpdates.length} queue(s) priorities`,
				);
			}

			return results;
		},

		onSuccess: (_, { workPoolName }) => {
			void queryClient.invalidateQueries({
				queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
			});
		},
	});
};
