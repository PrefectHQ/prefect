import {
	SchemaFormInputObject,
	SchemaFormInputObjectProps,
} from "./schema-form-input-object";
import { SchemaFormProvider } from "./schema-form-provider";
import { SchemaFormContext } from "./use-schema-form-context";

export type SchemaFormProps = SchemaFormContext & {
	errors: unknown;
	values: Record<string, unknown> | undefined;
	onValuesChange: (values: Record<string, unknown>) => void;
};

export const SchemaForm = (props: SchemaFormProps) => {
	const context: SchemaFormContext = {
		schema: props.schema,
		kinds: props.kinds,
		skipDefaultValueInitialization: props.skipDefaultValueInitialization,
	};

	const properties: SchemaFormInputObjectProps = {
		values: props.values,
		property: props.schema,
		onValuesChange: props.onValuesChange,
		errors: props.errors,
	};

	return (
		<div className="flex flex-col gap-4">
			<SchemaFormProvider {...context}>
				<SchemaFormInputObject {...properties} />
			</SchemaFormProvider>
		</div>
	);
};
