import { SchemaObject } from "openapi-typescript";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { asPrimitive } from "./utilities/asType";

export type SchemaFormInputUnknownProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject & { type: undefined };
	errors: unknown;
	id: string;
};

export function SchemaFormInputUnknown({
	value,
	onValueChange,
	property,
	errors,
	id,
}: SchemaFormInputUnknownProps) {
	if (isWithPrimitiveEnum(property)) {
		return (
			<SchemaFormInputEnum
				multiple={false}
				value={asPrimitive(value)}
				property={property}
				onValueChange={onValueChange}
				errors={errors}
				id={id}
			/>
		);
	}

	onValueChange({
		__prefect_kind: "json",
	});
}
