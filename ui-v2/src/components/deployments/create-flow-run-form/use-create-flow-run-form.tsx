import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { Deployment } from "@/api/deployments";
import {
	type CreateNewFlowRun,
	useDeploymentCreateFlowRun,
} from "@/api/flow-runs";
import { useSchemaForm } from "@/components/schemas";
import type { SchemaFormValues } from "@/components/schemas/types/values";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/utils/date";
import { createFakeFlowRunName } from "./create-fake-flow-run-name";

const formSchema = z.object({
	empirical_policy: z
		.object({
			/** Coerce to solve common issue of transforming a string number to a number type */
			retries: z.number().or(z.string()).pipe(z.coerce.number()).optional(),
			/** Coerce to solve common issue of transforming a string number to a number type */
			retry_delay: z.number().or(z.string()).pipe(z.coerce.number()).optional(),
		})
		.optional(),
	name: z.string().nonempty(),
	job_variables: z
		.string()
		.superRefine((val, ctx) => {
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
		})
		.optional(),
	state: z.object({
		message: z.string().optional(),
		state_details: z
			.object({
				scheduled_time: z
					.string()
					.nullable()
					.refine(
						(val) => {
							// nb: null value represents to run now
							if (!val) {
								return true;
							}
							const now = new Date();
							const selectedDateTime = new Date(val);
							return now.getTime() < selectedDateTime.getTime();
						},
						{ message: "Selected time must be set to the future" },
					),
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

const createDefaultValues = (): CreateFlowRunSchema => ({
	empirical_policy: {
		retries: 0,
		retry_delay: 0,
	},
	name: createFakeFlowRunName(),
	job_variables: "",
	state: {
		message: "",
		state_details: { scheduled_time: null },
	},
	tags: [],
	enforce_parameter_schema: true,
	parameter_openapi_schema: {},
});

export const useCreateFlowRunForm = (
	deployment: Deployment,
	overrideParameters: Record<string, unknown> | undefined,
) => {
	const navigate = useNavigate();
	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: createDefaultValues(),
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
		// Use parameters from an external source, if they're undefined, default to the deployment parameters
		setParametersFormValues(overrideParameters ?? deployment.parameters ?? {});

		// nb: Handle remaining form fields using react-hook-form
		form.reset({
			work_queue_name,
			tags,
			parameter_openapi_schema,
			enforce_parameter_schema,
			job_variables: job_variables ? JSON.stringify(job_variables) : "",
		});
	}, [form, deployment, setParametersFormValues, overrideParameters]);

	const onCreate = async (values: CreateFlowRunSchema) => {
		if (values.parameter_openapi_schema && values.enforce_parameter_schema) {
			try {
				await validateParametersForm({
					schema: values.parameter_openapi_schema,
				});
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
				id: deployment.id,
				...createPayload(parametersFormValues, values),
			},
			{
				onSuccess: (res) => {
					const message = `${values.name} scheduled to start ${values.state.state_details?.scheduled_time ? formatDate(values.state.state_details.scheduled_time, "dateTime") : "now"}`;
					toast.success(message, {
						action: (
							<Link to="/runs/flow-run/$id" params={{ id: res.id }}>
								<Button size="sm">View run</Button>
							</Link>
						),
					});
					void navigate({
						to: "/deployments/deployment/$id",
						params: { id: deployment.id },
					});
					form.reset(createDefaultValues());
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

// nb: Used to fill in default values required from poor openAPI typings. Not used in form
const DEFAULT_EMPIRICAL_POLICY = {
	resuming: false,
	max_retries: 0,
	retry_delay_seconds: 0,
};

// nb: Used to fill in default values required from poor openAPI typings. Not used in form
const DEFAULT_STATE = {
	type: "SCHEDULED" as const,
	state_details: {
		pause_reschedule: false,
		deferred: false,
		untrackable_result: false,
	},
};

function createPayload(
	parameterValues: SchemaFormValues,
	formValues: CreateFlowRunSchema,
): CreateNewFlowRun {
	const jobVariablesPayload = formValues.job_variables
		? (JSON.parse(formValues.job_variables) as Record<string, unknown>)
		: undefined;

	return {
		name: formValues.name,
		work_queue_name: formValues.work_queue_name || null,
		empirical_policy: {
			...DEFAULT_EMPIRICAL_POLICY,
			...formValues.empirical_policy,
		},
		state: {
			...DEFAULT_STATE,
			...formValues.state,
			state_details: {
				...DEFAULT_STATE.state_details,
				...formValues.state.state_details,
			},
		},
		job_variables: jobVariablesPayload,
		enforce_parameter_schema: formValues.enforce_parameter_schema,
		parameters: parameterValues,
	};
}
