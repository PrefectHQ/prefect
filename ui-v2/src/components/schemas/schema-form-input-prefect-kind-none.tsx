import { SchemaObject } from "openapi-typescript";
import { SchemaFormInput } from "./schema-form-input";
import { PrefectKindNull } from "./types/prefect-kind-value";

type SchemaFormInputPrefectKindNoneProps = {
	value: PrefectKindNull;
	onValueChange: (value: PrefectKindNull) => void;
	property: SchemaObject;
	errors: unknown;
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
