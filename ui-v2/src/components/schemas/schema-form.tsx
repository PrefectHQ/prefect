import { useCallback } from "react";
import {
	SchemaFormInputObject,
	type SchemaFormInputObjectProps,
} from "./schema-form-input-object";
import { SchemaFormProvider } from "./schema-form-provider";
import type { SchemaFormErrors } from "./types/errors";
import type { SchemaFormValues } from "./types/values";
import type { SchemaFormContext } from "./use-schema-form-context";

export type SchemaFormProps = SchemaFormContext & {
	errors: SchemaFormErrors;
	values: SchemaFormValues;
	onValuesChange: (values: SchemaFormValues) => void;
};

export const SchemaForm = ({
	schema,
	kinds,
	skipDefaultValueInitialization,
	values,
	onValuesChange,
	errors,
}: SchemaFormProps) => {
	const context: SchemaFormContext = {
		schema,
		kinds,
		skipDefaultValueInitialization,
	};

	const handleValuesChange = useCallback(
		(values: Record<string, unknown> | undefined) => {
			if (values === undefined) {
				onValuesChange({});
				return;
			}

			onValuesChange(values);
		},
		[onValuesChange],
	);

	const properties: Omit<SchemaFormInputObjectProps, "nested"> = {
		values,
		property: schema,
		onValuesChange: handleValuesChange,
		errors,
	};

	return (
		<div className="flex flex-col gap-4">
			<SchemaFormProvider {...context}>
				<SchemaFormInputObject {...properties} nested={false} />
			</SchemaFormProvider>
		</div>
	);
};
