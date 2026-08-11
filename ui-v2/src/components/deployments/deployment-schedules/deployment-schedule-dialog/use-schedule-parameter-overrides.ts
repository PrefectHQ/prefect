import { useMemo } from "react";
import { toast } from "sonner";
import type { Deployment, DeploymentSchedule } from "@/api/deployments";
import {
	useSchemaFormErrors,
	useSchemaFormValues,
	validateSchemaValues,
} from "@/components/schemas";
import type { SchemaFormErrors } from "@/components/schemas/types/errors";
import type { SchemaFormValues } from "@/components/schemas/types/values";

export type ScheduleParameterOverrides = {
	schema: Record<string, unknown> | undefined;
	values: SchemaFormValues;
	errors: SchemaFormErrors;
	setValues: (values: SchemaFormValues) => void;
	/** Validates the overrides against the deployment's parameter schema */
	validate: () => Promise<boolean>;
};

/**
 * Manages the parameter overrides of a deployment schedule.
 *
 * Overrides are partial by design, so the deployment's parameter schema is
 * relaxed to make every property optional before validating.
 */
export const useScheduleParameterOverrides = (
	deployment: Deployment,
	scheduleToEdit?: DeploymentSchedule,
): ScheduleParameterOverrides => {
	const schema = useMemo(() => {
		const { parameter_openapi_schema } = deployment;
		if (!parameter_openapi_schema) {
			return undefined;
		}
		return { ...parameter_openapi_schema, required: [] };
	}, [deployment]);

	const [values, setValues] = useSchemaFormValues(scheduleToEdit?.parameters);
	const [errors, setErrors] = useSchemaFormErrors();

	const validate = async () => {
		if (!schema) {
			return true;
		}
		try {
			const { errors: validationErrors, valid } = await validateSchemaValues(
				schema,
				values,
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
