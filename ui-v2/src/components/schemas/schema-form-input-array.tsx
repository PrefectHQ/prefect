import type {
	ArraySubtype,
	ReferenceObject,
	SchemaObject,
} from "openapi-typescript";
import { SchemaFormInputArrayList } from "./schema-form-input-array-list";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import type { SchemaFormErrors } from "./types/errors";
import { isWithPrimitiveEnum } from "./types/schemas";
import { useSchemaFormContext } from "./use-schema-form-context";
import { asArray } from "./utilities/asType";
import { isItemsObject, isRecord, isReferenceObject } from "./utilities/guards";
import { getSchemaDefinition } from "./utilities/mergeSchemaPropertyDefinition";

type SchemaFormInputArrayProps = {
	values: unknown[] | undefined;
	onValuesChange: (values: unknown[] | undefined) => void;
	property: SchemaObject & ArraySubtype;
	errors: SchemaFormErrors;
	id: string;
};

export function SchemaFormInputArray({
	values,
	property,
	onValuesChange,
	errors,
	id,
}: SchemaFormInputArrayProps) {
	const { schema } = useSchemaFormContext();

	function handleValuesChange(values: unknown[] | undefined) {
		if (values === undefined || values.length === 0) {
			onValuesChange(undefined);
			return;
		}

		onValuesChange(values);
	}

	if (isItemsObject(property) && isRecord(property.items)) {
		let items: SchemaObject | ReferenceObject = property.items;

		if (isReferenceObject(items)) {
			items = getSchemaDefinition(schema, items.$ref);
		}

		if (isWithPrimitiveEnum(items)) {
			const merged = { ...property, ...items };

			return (
				<SchemaFormInputEnum
					multiple={true}
					values={asArray(values, "primitive")}
					property={merged}
					onValuesChange={handleValuesChange}
					id={id}
				/>
			);
		}
	}

	return (
		<SchemaFormInputArrayList
			property={property}
			values={values}
			onValuesChange={handleValuesChange}
			errors={errors}
		/>
	);
}
