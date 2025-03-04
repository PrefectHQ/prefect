import { Deployment, useUpdateDeployment } from "@/api/deployments";
import { useSchemaForm } from "@/components/schemas";
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
	job_variables: z.string().superRefine((val, ctx) => {
		try {
			if (!val) {
				return;
			}
			return JSON.parse(val) as Record<string, unknown>;
		} catch (err) {
			console.error(err);
			ctx.addIssue({ code: "custom", message: "Invalid JSON" });
			return z.NEVER;
		}
	}),
	enforce_parameter_schema: z.boolean(),
	parameter_openapi_schema: z
		.record(z.unknown())
		.optional()
		.nullable()
		.readonly(),
});

export type DeploymentFormSchema = z.infer<typeof formSchema>;

export const useDeploymentForm = (deployment: Deployment) => {
	const navigate = useNavigate();
	const form = useForm({ resolver: zodResolver(formSchema) });
	const {
		values: parametersFormValues,
		setValues: setParametersFormValues,
		errors: parameterFormErrors,
		validateForm: validateParametersForm,
	} = useSchemaForm();
	const { updateDeployment } = useUpdateDeployment();

	// syncs form state to deployment to update
	useEffect(() => {
		const {
			description,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables,
		} = deployment;

		// nb: parameter form state and validation is handled separately using SchemaForm
		// parameters has poor typings from openAPI
		setParametersFormValues(deployment.parameters as Record<string, unknown>);

		// nb: Handle remaining form fields using react-hook-form
		form.reset({
			description,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables: job_variables ? JSON.stringify(job_variables) : "",
		});
	}, [form, deployment, setParametersFormValues]);

	const onSave = async (values: DeploymentFormSchema) => {
		const {
			job_variables,
			description,
			work_pool_name,
			work_queue_name,
			tags,
			enforce_parameter_schema,
			concurrency_options,
			parameter_openapi_schema,
		} = values;

		const jobVariablesPayload = job_variables
			? (JSON.parse(job_variables) as Record<string, unknown>)
			: undefined;

		if (parameter_openapi_schema && enforce_parameter_schema) {
			try {
				await validateParametersForm({ schema: parameter_openapi_schema });
			} catch (err) {
				const message = "Unknown error while updating validating schema.";
				toast.error(message);
				console.error(message, err);
			}
		}

		// Early exit if there's errors
		if (parameterFormErrors.length > 0) {
			return;
		}

		updateDeployment(
			{
				id: deployment.id,
				paused: deployment.paused,
				description,
				// If value is "", set as null
				work_pool_name: work_pool_name || null,
				// If value is "", set as null
				work_queue_name: work_queue_name || null,
				tags,
				enforce_parameter_schema,
				// @ts-expect-error Expecting TS error from poor openAPI typings
				parameters: parametersFormValues,
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
					toast.error(message);
				},
			},
		);
	};

	return {
		form,
		onSave,
		parametersFormValues,
		setParametersFormValues,
		parameterFormErrors,
	};
};
