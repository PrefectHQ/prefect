import { getQueryService } from "@/api/service";
import { queryKeyFactory } from "@/api/work-pools/work-pools";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

/**
 * Hook for pausing a work pool
 * @returns Mutation for pausing a work pool
 */
export const usePauseWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: pauseWorkPool, ...rest } = useMutation({
		mutationFn: async (name: string) => {
			await getQueryService().PATCH("/work_pools/{name}", {
				params: { path: { name } },
				body: {
					is_paused: true,
				},
			});
		},
		onSuccess: (_, name) => {
			void queryClient.invalidateQueries({ queryKey: queryKeyFactory.all() });
			void queryClient.invalidateQueries({
				queryKey: queryKeyFactory.detail(name),
			});
			toast.success(`${name} paused`);
		},
		onError: (error) => {
			toast.error(
				`Failed to pause work pool: ${error instanceof Error ? error.message : "Unknown error"}`,
			);
		},
	});

	return { pauseWorkPool, ...rest };
};

/**
 * Hook for resuming a work pool
 * @returns Mutation for resuming a work pool
 */
export const useResumeWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: resumeWorkPool, ...rest } = useMutation({
		mutationFn: async (name: string) => {
			await getQueryService().PATCH("/work_pools/{name}", {
				params: { path: { name } },
				body: {
					is_paused: false,
				},
			});
		},
		onSuccess: (_, name) => {
			void queryClient.invalidateQueries({ queryKey: queryKeyFactory.all() });
			void queryClient.invalidateQueries({
				queryKey: queryKeyFactory.detail(name),
			});
			toast.success(`${name} resumed`);
		},
		onError: (error) => {
			toast.error(
				`Failed to resume work pool: ${error instanceof Error ? error.message : "Unknown error"}`,
			);
		},
	});

	return { resumeWorkPool, ...rest };
};

/**
 * Hook for deleting a work pool
 * @returns Mutation for deleting a work pool
 */
export const useDeleteWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteWorkPool, ...rest } = useMutation({
		mutationFn: async (name: string) => {
			await getQueryService().DELETE("/work_pools/{name}", {
				params: { path: { name } },
			});
		},
		onSuccess: (_, name) => {
			void queryClient.invalidateQueries({ queryKey: queryKeyFactory.all() });
			toast.success(`${name} deleted`);
		},
		onError: (error) => {
			toast.error(
				`Failed to delete work pool: ${error instanceof Error ? error.message : "Unknown error"}`,
			);
		},
	});

	return { deleteWorkPool, ...rest };
};
