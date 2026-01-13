import { useCallback, useEffect, useRef, useState } from "react";
import useDebounceCallback from "@/hooks/use-debounce-callback";
import { validateSchemaValues } from "../utilities/validate";
import { useSchemaFormErrors } from "./useSchemaFormErrors";
import { useSchemaFormValues } from "./useSchemaValues";

/**
 * Hook wrapper to cover most cases in setting form values, validating, and triggering errors
 *
 * @returns hook with validation, errors, and values to be plugged into a component
 *
 * @example
 * ```tsx
 *	const App = () => {
 * 		const { enforce_parameter_schema, parameter_openapi_schema } = useGetDeployment('deployment-id-0');
 * 		const { setValues, values, errors, validateForm } = useSchemaForm();
 *
 * 		const handleValidateForm = () => validateForm({ schema: parameter_openapi_schema });
 *
 * 		return (
 * 			<div>
 * 				<SchemaForm
 * 					schema={parameter_openapi_schema}
 * 					values={values}
 * 					errors={errors}
 * 					onValuesChange={setValues}
 * 					kinds={["json"]}
 * 				/>
 * 				<button onClick={handleValidateForm}>Validate</button>
 * 			</div>
 * 		);
 * };
 * ```
 */
export const useSchemaForm = () => {
	const [values, setValues] = useSchemaFormValues();
	const [errors, setErrors] = useSchemaFormErrors();
	const [hasValidatedOnce, setHasValidatedOnce] = useState(false);
	const schemaRef = useRef<Record<string, unknown> | null>(null);

	const runValidation = useCallback(
		async (options?: { throwOnError?: boolean }) => {
			if (!schemaRef.current) {
				return;
			}

			try {
				const { errors: validationErrors, valid } = await validateSchemaValues(
					schemaRef.current,
					values,
				);
				if (valid) {
					setErrors([]);
				} else {
					setErrors(validationErrors);
				}
			} catch {
				if (options?.throwOnError) {
					throw new Error("Server error occurred validating schema");
				}
			}
		},
		[values, setErrors],
	);

	const debouncedValidation = useDebounceCallback(runValidation, 1000);

	useEffect(() => {
		if (hasValidatedOnce && errors.length > 0 && schemaRef.current) {
			debouncedValidation();
		}
	}, [hasValidatedOnce, errors.length, debouncedValidation]);

	const validateForm = async ({
		schema,
	}: {
		schema: Record<string, unknown>;
	}) => {
		schemaRef.current = schema;
		await runValidation({ throwOnError: true });
		setHasValidatedOnce(true);
	};

	return {
		setValues,
		values,
		errors,
		validateForm,
	};
};
