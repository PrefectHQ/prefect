import { SchemaFormInput } from "./schema-form-input";
import { PrefectKindNull } from "./types/prefect-kind-value";
import { PrefectSchemaObject } from "./types/schemas";

type SchemaFormInputPrefectKindNoneProps = {
	value: PrefectKindNull;
	onValueChange: (value: PrefectKindNull) => void;
	property: PrefectSchemaObject;
	errors: unknown;
};

export function SchemaFormInputPrefectKindNone({
	value,
	onValueChange,
	property,
	errors,
}: SchemaFormInputPrefectKindNoneProps) {
	const onChange = (value: unknown) => {
		onValueChange({
			__prefect_kind: "none",
			value: value || undefined,
		});
	};

	return (
		<SchemaFormInput
			value={value.value}
			onValueChange={onChange}
			errors={errors}
			property={property}
		/>
	);
}
