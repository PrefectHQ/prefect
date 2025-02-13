import { SchemaObject } from "openapi-typescript";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { asPrimitive } from "./utilities/asType";

export type SchemaFormInputUnknownProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject & { type: undefined };
	errors: unknown;
};

export function SchemaFormInputUnknown({
	value,
	onValueChange,
	property,
	errors,
}: SchemaFormInputUnknownProps) {
	if (isWithPrimitiveEnum(property)) {
		return (
			<SchemaFormInputEnum
				multiple={false}
				value={asPrimitive(value)}
				property={property}
				onValueChange={onValueChange}
				errors={errors}
			/>
		);
	}

	// need to convert to a prefect-kind json automatically
	throw new Error("Schema type not implemented");
}
