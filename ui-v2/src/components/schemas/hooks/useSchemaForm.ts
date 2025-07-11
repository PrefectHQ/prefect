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

	const validateForm = async ({
		schema,
	}: {
		schema: Record<string, unknown>;
	}) => {
		try {
			const { errors, valid } = await validateSchemaValues(schema, values);
			if (valid) {
				setErrors([]);
			} else {
				setErrors(errors);
			}
		} catch {
			throw new Error("Server error occurred validating schema");
		}
	};

	return {
		setValues,
		values,
		errors,
		validateForm,
	};
};
