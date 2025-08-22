import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
	useDeleteWorkPoolQueueMutation,
	workPoolQueuesQueryKeyFactory,
} from "@/api/work-pool-queues";

type BulkDeleteParams = {
	workPoolName: string;
	queueNames: string[];
};

export const useBulkDeleteWorkPoolQueuesMutation = () => {
	const queryClient = useQueryClient();
	const deleteQueueMutation = useDeleteWorkPoolQueueMutation();

	return useMutation({
		mutationFn: async ({ workPoolName, queueNames }: BulkDeleteParams) => {
			// Delete queues sequentially to avoid overwhelming the API
			const results = [];
			for (const queueName of queueNames) {
				try {
					await new Promise<void>((resolve, reject) => {
						deleteQueueMutation.mutate(
							{ workPoolName, queueName },
							{
								onSuccess: () => resolve(),
								onError: reject,
							},
						);
					});
					results.push({ queueName, success: true });
				} catch (error) {
					results.push({ queueName, success: false, error });
				}
			}

			const failedQueues = results.filter((r) => !r.success);
			if (failedQueues.length > 0) {
				throw new Error(
					`Failed to delete ${failedQueues.length} queue(s): ${failedQueues.map((f) => f.queueName).join(", ")}`,
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
