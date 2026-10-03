import { useMemo } from "react";
import { toast } from "sonner";
import type { Deployment, DeploymentSchedule } from "@/api/deployments";
import {
	type PrefectSchemaObject,
	useSchemaFormErrors,
	useSchemaFormValues,
	validateSchemaValues,
} from "@/components/schemas";
import type { SchemaFormErrors } from "@/components/schemas/types/errors";
import type { SchemaFormValues } from "@/components/schemas/types/values";
import { isRecord } from "@/components/schemas/utilities/guards";

type ParameterSchema = Record<string, unknown> & PrefectSchemaObject;

const isObjectSchema = (
	schema: Record<string, unknown>,
): schema is ParameterSchema =>
	schema.type === "object" &&
	(schema.properties === undefined || isRecord(schema.properties));

export type ScheduleParameterOverrides = {
	schema: ParameterSchema | undefined;
	values: SchemaFormValues;
	errors: SchemaFormErrors;
	setValues: (values: SchemaFormValues) => void;
	/** Validates the overrides against the deployment's parameter schema */
	validate: () => Promise<boolean>;
};

/**
 * Manages the parameter overrides of a deployment schedule.
 *
 * Overrides are partial by design, so every property is optional in the form's
 * schema. Scheduled runs receive the deployment parameters merged with the
 * overrides, so that merged dictionary is what gets validated.
 */
export const useScheduleParameterOverrides = (
	deployment: Deployment,
	scheduleToEdit?: DeploymentSchedule,
): ScheduleParameterOverrides => {
	const deploymentSchema = useMemo(() => {
		const { parameter_openapi_schema } = deployment;
		if (!parameter_openapi_schema) {
			return undefined;
		}
		return isObjectSchema(parameter_openapi_schema)
			? parameter_openapi_schema
			: undefined;
	}, [deployment]);

	const schema = useMemo(
		() =>
			deploymentSchema ? { ...deploymentSchema, required: [] } : undefined,
		[deploymentSchema],
	);

	const [values, setValues] = useSchemaFormValues(scheduleToEdit?.parameters);
	const [errors, setErrors] = useSchemaFormErrors();

	const validate = async () => {
		if (!deploymentSchema || !deployment.enforce_parameter_schema) {
			return true;
		}
		try {
			const { errors: validationErrors, valid } = await validateSchemaValues(
				deploymentSchema,
				{ ...deployment.parameters, ...values },
			);
			setErrors(valid ? [] : validationErrors);
			return valid;
		} catch {
			toast.error("Unknown error while validating parameter overrides.");
			return false;
		}
	};

	return { schema, values, errors, setValues, validate };
};
