import { Deployment, useUpdateDeployment } from "@/api/deployments";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

const formSchema = z.object({
	description: z.string().nullable().optional(),
	work_pool_name: z.string().nullable().optional(),
	work_queue_name: z.string().nullable().optional(),
	tags: z.array(z.string()).optional(),
	/** Coerce to solve common issue of transforming a string to undefined */
	concurrency_options: z
		.object({ collision_strategy: z.enum(["ENQUEUE", "CANCEL_NEW"]) })
		.nullable()
		.optional(),
	enforce_parameter_schema: z.boolean(),
	job_variables: z.string().superRefine((val, ctx) => {
		try {
			if (!val) {
				return;
			}
			return JSON.parse(val) as Record<string, unknown>;
			// eslint-disable-next-line @typescript-eslint/no-unused-vars
		} catch (e) {
			ctx.addIssue({ code: "custom", message: "Invalid JSON" });
			return z.NEVER;
		}
	}),
});
export type DeploymentFormSchema = z.infer<typeof formSchema>;

export const useDeploymentForm = (deployment: Deployment) => {
	const navigate = useNavigate();
	const form = useForm({ resolver: zodResolver(formSchema) });

	const { updateDeployment } = useUpdateDeployment();

	// syncs form state to deployment to update
	useEffect(() => {
		const {
			description,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
			enforce_parameter_schema,
			job_variables,
		} = deployment;

		form.reset({
			description,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
			enforce_parameter_schema,
			job_variables: job_variables ? JSON.stringify(job_variables) : "",
		});
	}, [form, deployment]);

	const onSave = (values: DeploymentFormSchema) => {
		const {
			job_variables,
			description,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
		} = values;

		const jobVariablesPayload = job_variables
			? (JSON.parse(job_variables) as Record<string, unknown>)
			: undefined;

		updateDeployment(
			{
				id: deployment.id,
				paused: deployment.paused,
				description,
				// If value is "", set as null
				work_pool_name: work_pool_name || null,
				// If value is "", set as nuill
				work_queue_name: work_queue_name || null,
				tags,
				concurrency_options,
				// @ts-expect-error Expecting TS error from poor openAPI typings
				job_variables: jobVariablesPayload,
			},
			{
				onSuccess: () => {
					toast.success("Deployment updated");
					void navigate({
						to: "/deployments/deployment/$id",
						params: { id: deployment.id },
					});
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while updating deployment.";
					console.error(message);
				},
			},
		);
	};

	return { form, onSave };
};
