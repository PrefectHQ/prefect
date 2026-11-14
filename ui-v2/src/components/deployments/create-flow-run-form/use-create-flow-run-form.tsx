import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
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
import { isRecord } from "@/components/schemas/utilities/guards";
import { removePrefectKindValues } from "@/components/schemas/utilities/removePrefectKindValues";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/utils/date";
import { createFakeFlowRunName } from "./create-fake-flow-run-name";

const formSchema = z.object({
	empirical_policy: z
		.object({
			/** Coerce to solve common issue of transforming a string number to a number type */
			retries: z
				.number()
				.or(z.string())
				.pipe(z.coerce.number<string | number>())
				.optional(),
			/** Coerce to solve common issue of transforming a string number to a number type */
			retry_delay: z
				.number()
				.or(z.string())
				.pipe(z.coerce.number<string | number>())
				.optional(),
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
				JSON.parse(val);
			} catch (err) {
				console.error(err);
				ctx.addIssue({ code: "custom", message: "Invalid JSON" });
				return;
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
		.record(z.string(), z.unknown())
		.optional()
		.nullable()
		.readonly(),
});

export type CreateFlowRunSchema = z.infer<typeof formSchema>;

export type ParametersInputMode = "form" | "json";

export type AdditionalOptionsOverrides = {
	message?: string;
	tags?: string[];
	work_queue_name?: string | null;
	retries?: number | null;
	retry_delay?: number | null;
	job_variables?: Record<string, unknown> | null;
};

// nb: Parameter values are managed separately by `useSchemaForm`; this only
// builds defaults for the react-hook-form portion of the create flow run form.
const createDefaultValues = (
	deployment: Deployment,
	overrideAdditionalOptions?: AdditionalOptionsOverrides,
): CreateFlowRunSchema => {
	const base = {
		empirical_policy: {
			retries: 0,
			retry_delay: 0,
		},
		name: createFakeFlowRunName(),
		job_variables: deployment.job_variables
			? JSON.stringify(deployment.job_variables)
			: "",
		state: {
			message: "",
			state_details: { scheduled_time: null },
		},
		tags: deployment.tags ?? [],
		work_queue_name: deployment.work_queue_name,
		enforce_parameter_schema: deployment.enforce_parameter_schema,
		parameter_openapi_schema: deployment.parameter_openapi_schema,
	};

	if (!overrideAdditionalOptions) {
		return base;
	}

	return {
		...base,
		state: {
			...base.state,
			message: overrideAdditionalOptions.message ?? base.state.message,
		},
		tags: overrideAdditionalOptions.tags ?? base.tags,
		work_queue_name:
			overrideAdditionalOptions.work_queue_name ?? base.work_queue_name,
		empirical_policy: {
			...base.empirical_policy,
			retries:
				overrideAdditionalOptions.retries ?? base.empirical_policy.retries,
			retry_delay:
				overrideAdditionalOptions.retry_delay ??
				base.empirical_policy.retry_delay,
		},
		job_variables: overrideAdditionalOptions.job_variables
			? JSON.stringify(overrideAdditionalOptions.job_variables)
			: base.job_variables,
	};
};

export const useCreateFlowRunForm = (
	deployment: Deployment,
	overrideParameters: Record<string, unknown> | undefined,
	overrideAdditionalOptions?: AdditionalOptionsOverrides,
) => {
	const navigate = useNavigate();
	// Capture initial form values once so subsequent deployment refetches
	// (driven by `refetchInterval` / `refetchOnWindowFocus`) do not overwrite
	// in-flight user edits. See OSS-7952.
	const [initialFormValues] = useState(() =>
		createDefaultValues(deployment, overrideAdditionalOptions),
	);
	const hasParametersSchema = Boolean(deployment.parameter_openapi_schema);
	const [initialParameterValues] = useState(
		() => overrideParameters ?? deployment.parameters ?? {},
	);
	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: initialFormValues,
	});
	const {
		values: parametersFormValues,
		setValues: setParametersFormValues,
		errors: parameterFormErrors,
		validateForm: validateParametersForm,
	} = useSchemaForm(initialParameterValues);

	const initialParametersInputMode: ParametersInputMode = hasParametersSchema
		? "form"
		: "json";
	const [parametersInputMode, setParametersInputMode] =
		useState<ParametersInputMode>(initialParametersInputMode);
	const [parametersJson, setParametersJson] = useState(() =>
		hasParametersSchema ? "" : formatParametersJson(initialParameterValues),
	);
	const [parametersJsonError, setParametersJsonError] = useState<string | null>(
		null,
	);

	const { createDeploymentFlowRun } = useDeploymentCreateFlowRun();

	const onParametersInputModeChange = (mode: ParametersInputMode) => {
		if (mode === parametersInputMode) {
			return;
		}

		if (mode === "json") {
			const values = removePrefectKindValues(parametersFormValues);
			if (isRecord(values)) {
				setParametersFormValues(values);
			}
			setParametersJson(formatParametersJson(values));
			setParametersJsonError(null);
		} else if (!hasParametersSchema || parametersJsonError) {
			return;
		}

		setParametersInputMode(mode);
	};

	// Valid JSON is applied to the schema form values right away, so validation,
	// submission, and switching back to the form all use the latest JSON document.
	const onParametersJsonChange = (value: string) => {
		setParametersJson(value);

		let parsed: unknown;
		try {
			parsed = JSON.parse(value);
		} catch {
			setParametersJsonError("Invalid JSON");
			return;
		}

		if (!isRecord(parsed)) {
			setParametersJsonError("Parameters must be a JSON object");
			return;
		}

		setParametersJsonError(null);
		setParametersFormValues(parsed);
	};

	const onCreate = async (values: CreateFlowRunSchema) => {
		if (parametersInputMode === "json" && parametersJsonError) {
			return;
		}

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
					form.reset(createDefaultValues(deployment));
					setParametersFormValues(
						overrideParameters ?? deployment.parameters ?? {},
					);
					setParametersInputMode(initialParametersInputMode);
					setParametersJson(
						hasParametersSchema
							? ""
							: formatParametersJson(
									overrideParameters ?? deployment.parameters ?? {},
								),
					);
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
		parametersInputMode,
		onParametersInputModeChange,
		parametersJson,
		onParametersJsonChange,
		parametersJsonError,
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

function formatParametersJson(values: unknown): string {
	return JSON.stringify(values, null, 2);
}

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
		tags: formValues.tags,
		job_variables: jobVariablesPayload,
		enforce_parameter_schema: formValues.enforce_parameter_schema,
		parameters: parameterValues,
	};
}
