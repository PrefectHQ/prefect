import type { Deployment } from "@/api/deployments";
import { useDeploymentCreateFlowRun } from "@/api/flow-runs";
import { useSchemaForm } from "@/components/schemas";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/utils/date";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { createFakeFlowRunName } from "./create-fake-flow-run-name";

const formSchema = z.object({
	empirical_policy: z.object({
		retries: z.number().nullable(),
		retry_delay: z.number().nullable(),
		/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
		resuming: z.literal(false).readonly(),
		/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
		max_retries: z.literal(0).readonly(),
		/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
		retry_delay_seconds: z.literal(0).readonly(),
	}),
	name: z.string(),
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
	state: z.object({
		/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
		type: z.literal("SCHEDULED").readonly(),
		message: z.string().optional(),
		state_details: z
			.object({
				scheduled_time: z.string().optional(),
				/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
				pause_reschedule: z.literal(false).readonly(),
				/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
				deferred: z.literal(false).readonly(),
				/** nb: due to poor openAPI typing, need add this to schema. This will not be set, but just passed in the payload using the default value */
				untrackable_result: z.literal(false).readonly(),
			})
			.optional(),
	}),
	tags: z.array(z.string()).optional(),
	work_queue_name: z.string().nullable().optional(),
	enforce_parameter_schema: z.boolean(),
	parameter_openapi_schema: z
		.record(z.unknown())
		.optional()
		.nullable()
		.readonly(),
});

export type CreateFlowRunSchema = z.infer<typeof formSchema>;

const DEFAULT_VALUES: CreateFlowRunSchema = {
	empirical_policy: {
		retries: null,
		retry_delay: null,
		resuming: false,
		max_retries: 0,
		retry_delay_seconds: 0,
	},
	name: createFakeFlowRunName(),
	job_variables: "",
	state: {
		message: "",
		type: "SCHEDULED",
		state_details: {
			pause_reschedule: false,
			deferred: false,
			untrackable_result: false,
		},
	},
	tags: [],
	enforce_parameter_schema: true,
	parameter_openapi_schema: {},
};

export const useCreateFlowRunForm = (deployment: Deployment) => {
	const navigate = useNavigate();
	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: DEFAULT_VALUES,
	});
	const {
		values: parametersFormValues,
		setValues: setParametersFormValues,
		errors: parameterFormErrors,
		validateForm: validateParametersForm,
	} = useSchemaForm();

	const { createDeploymentFlowRun } = useDeploymentCreateFlowRun();

	// syncs form state to deployment to update
	useEffect(() => {
		const {
			work_queue_name,
			tags,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables,
		} = deployment;

		// nb: parameter form state and validation is handled separately using SchemaForm
		// parameters has poor typings from openAPI
		setParametersFormValues(deployment.parameters as Record<string, unknown>);

		// nb: Handle remaining form fields using react-hook-form
		form.reset({
			work_queue_name,
			tags,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables: job_variables ? JSON.stringify(job_variables) : "",
		});
	}, [form, deployment, setParametersFormValues]);

	const onCreate = async (values: CreateFlowRunSchema) => {
		const {
			empirical_policy,
			enforce_parameter_schema,
			job_variables,
			name,
			parameter_openapi_schema,
			state,
			tags,
			work_queue_name,
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

		createDeploymentFlowRun(
			{
				enforce_parameter_schema,
				empirical_policy,
				state,
				flow_id: deployment.flow_id,
				// @ts-expect-error Expecting TS error from poor openAPI typings
				job_variables: jobVariablesPayload,
				name,
				// @ts-expect-error Expecting TS error from poor openAPI typings
				parameters: parametersFormValues,
				parameter_openapi_schema,
				tags,
				// If value is "", set as null
				work_queue_name: work_queue_name || null,
			},
			{
				onSuccess: (res) => {
					const message = `${name} scheduled to start ${state.state_details?.scheduled_time ? formatDate(state.state_details?.scheduled_time, "dateTime") : "now"}`;
					toast.success(message, {
						action: (
							<Link to="/runs/flow-run/$id" params={{ id: res.id }}>
								<Button size="sm">View run</Button>
							</Link>
						),
						description: (
							<p>
								<span className="font-bold">{res.name}</span> scheduled to start{" "}
								<span className="font-bold">now</span>
							</p>
						),
					});
					void navigate({
						to: "/deployments/deployment/$id",
						params: { id: deployment.id },
					});
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while creating flow run.";
					console.error(message);
					toast.error(message);
				},
			},
		);
	};

	return {
		form,
		onCreate,
		parametersFormValues,
		setParametersFormValues,
		parameterFormErrors,
	};
};
