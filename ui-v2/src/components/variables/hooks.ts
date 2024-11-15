import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { useToast } from "@/hooks/use-toast";
import { useMutation, useQueryClient } from "@tanstack/react-query";

type UseCreateVariableProps = {
	onSuccess: () => void;
	onError: (error: Error) => void;
};

export const useCreateVariable = ({
	onSuccess,
	onError,
}: UseCreateVariableProps) => {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: (variable: components["schemas"]["VariableCreate"]) => {
			return getQueryService().POST("/variables/", {
				body: variable,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "variables",
				}),
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "total-variable-count",
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable created",
			});
			onSuccess();
		},
		onError,
	});
};

type UseUpdateVariableProps = {
	existingVariable?: components["schemas"]["Variable"];
	onSuccess: () => void;
	onError: (error: Error) => void;
};

export const useUpdateVariable = ({
	existingVariable,
	onSuccess,
	onError,
}: UseUpdateVariableProps) => {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: (variable: components["schemas"]["VariableUpdate"]) => {
			if (!existingVariable?.id) throw new Error("Variable ID is required");
			return getQueryService().PATCH("/variables/{id}", {
				params: { path: { id: existingVariable.id } },
				body: variable,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "variables",
				}),
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "total-variable-count",
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable updated",
			});
			onSuccess();
		},
		onError,
	});
};
