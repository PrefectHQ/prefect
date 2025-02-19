import { SchemaObject } from "openapi-typescript";
import { SchemaFormInput } from "./schema-form-input";
import { SchemaFormErrors } from "./types/errors";
import { PrefectKindNull } from "./types/prefect-kind-value";
type SchemaFormInputPrefectKindNoneProps = {
	value: PrefectKindNull;
	onValueChange: (value: PrefectKindNull) => void;
	property: SchemaObject;
	errors: SchemaFormErrors;
	id: string;
};

export function SchemaFormInputPrefectKindNone({
	value,
	onValueChange,
	property,
	errors,
	id,
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
			id={id}
		/>
	);
}
