import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import {
	type Deployment,
	useCreateDeployment,
	useUpdateDeployment,
} from "@/api/deployments";
import { useSchemaForm } from "@/components/schemas";

type FormMode = "edit" | "duplicate";

const createFormSchema = (
	deployment: Deployment,
	{ mode }: { mode: FormMode },
) =>
	z.object({
		name: z.string().refine(
			(value) => {
				if (mode === "edit") {
					return true;
				}
				return value !== deployment.name;
			},
			{ message: "Name must be different from the original deployment" },
		),
		description: z.string().nullable().optional(),
		work_pool_name: z.string().nullable().optional(),
		work_queue_name: z.string().nullable().optional(),
		tags: z.array(z.string()).optional(),
		concurrency_options: z
			.object({
				collision_strategy: z.enum(["ENQUEUE", "CANCEL_NEW"]).optional(),
			})
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
		global_concurrency_limit_id: z.string().uuid().optional().nullable(),
	});

export type DeploymentFormSchema = z.infer<ReturnType<typeof createFormSchema>>;

const DEFAULT_VALUES: DeploymentFormSchema = {
	name: "",
	description: "",
	tags: [],
	job_variables: "",
	enforce_parameter_schema: true,
	global_concurrency_limit_id: null,
};

export const useDeploymentForm = (
	deployment: Deployment,
	{ mode }: { mode: FormMode },
) => {
	const navigate = useNavigate();
	const form = useForm({
		resolver: zodResolver(createFormSchema(deployment, { mode })),
		defaultValues: DEFAULT_VALUES,
	});
	const {
		values: parametersFormValues,
		setValues: setParametersFormValues,
		errors: parameterFormErrors,
		validateForm: validateParametersForm,
	} = useSchemaForm();

	const { createDeployment } = useCreateDeployment();
	const { updateDeployment } = useUpdateDeployment();

	// syncs form state to deployment to update
	useEffect(() => {
		const {
			name,
			description,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables,
			global_concurrency_limit,
		} = deployment;

		// nb: parameter form state and validation is handled separately using SchemaForm
		// parameters has poor typings from openAPI
		setParametersFormValues(deployment.parameters as Record<string, unknown>);

		// nb: Handle remaining form fields using react-hook-form
		form.reset({
			description,
			name,
			work_pool_name,
			work_queue_name,
			tags,
			concurrency_options,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables: job_variables ? JSON.stringify(job_variables) : "",
			global_concurrency_limit_id: global_concurrency_limit?.id,
		});
	}, [form, deployment, setParametersFormValues]);

	const onSave = async (values: DeploymentFormSchema) => {
		const {
			name,
			job_variables,
			description,
			work_pool_name,
			work_queue_name,
			tags,
			enforce_parameter_schema,
			concurrency_options,
			parameter_openapi_schema,
			global_concurrency_limit_id,
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

		const concurrencyOptions = concurrency_options?.collision_strategy
			? { collision_strategy: concurrency_options.collision_strategy }
			: undefined;

		switch (mode) {
			case "duplicate":
				createDeployment(
					{
						concurrency_options: concurrencyOptions,
						description,
						enforce_parameter_schema,
						flow_id: deployment.flow_id,
						job_variables: jobVariablesPayload,
						name,
						parameters: parametersFormValues,
						parameter_openapi_schema,
						paused: deployment.paused,
						tags,
						// If value is "", set as null
						work_pool_name: work_pool_name || null,
						// If value is "", set as null
						work_queue_name: work_queue_name || null,
						global_concurrency_limit_id,
					},
					{
						onSuccess: ({ id }) => {
							toast.success("Deployment created");
							void navigate({
								to: "/deployments/deployment/$id",
								params: { id },
							});
						},
						onError: (error) => {
							const message =
								error.message || "Unknown error while creating deployment.";
							console.error(message);
							toast.error(message);
						},
					},
				);
				break;
			case "edit":
				updateDeployment(
					{
						concurrency_options: concurrencyOptions,
						description,
						enforce_parameter_schema,
						id: deployment.id,
						job_variables: jobVariablesPayload,
						parameters: parametersFormValues,
						paused: deployment.paused,
						tags,
						// If value is "", set as null
						work_pool_name: work_pool_name || null,
						// If value is "", set as null
						work_queue_name: work_queue_name || null,
						global_concurrency_limit_id,
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
				break;
		}
	};

	return {
		form,
		onSave,
		parametersFormValues,
		setParametersFormValues,
		parameterFormErrors,
	};
};
