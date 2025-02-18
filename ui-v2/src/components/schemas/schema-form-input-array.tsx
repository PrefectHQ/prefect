import { ArraySubtype, SchemaObject } from "openapi-typescript";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { asArray } from "./utilities/asType";
import { isRecord, isReferenceObject } from "./utilities/guards";

type SchemaFormInputArrayProps = {
	values: unknown[] | undefined;
	onValuesChange: (values: unknown[] | undefined) => void;
	property: SchemaObject & ArraySubtype;
	errors: unknown;
};

export function SchemaFormInputArray({
	values,
	property,
	onValuesChange,
	errors,
}: SchemaFormInputArrayProps) {
	if ("items" in property && property.items && isRecord(property.items)) {
		if (isReferenceObject(property.items)) {
			throw new Error("not implemented");
		}

		if (isWithPrimitiveEnum(property.items)) {
			const merged = { ...property, ...property.items };

			return (
				<SchemaFormInputEnum
					multiple={true}
					values={asArray(values, "primitive")}
					property={merged}
					onValuesChange={onValuesChange}
					errors={errors}
				/>
			);
		}
	}

	// todo: properties of type "array" with no enum items
	throw new Error("not implemented");
}
