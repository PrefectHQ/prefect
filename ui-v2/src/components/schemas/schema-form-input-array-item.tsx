import { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useId } from "react";
import { SchemaFormInput } from "./schema-form-input";
import { SchemaFormErrors } from "./types/errors";
import { useSchemaFormContext } from "./use-schema-form-context";
import { isArray, isReferenceObject } from "./utilities/guards";
import { getSchemaDefinition } from "./utilities/mergeSchemaPropertyDefinition";

export type SchemaFormInputArrayItemProps = {
	items: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	value: unknown;
	onValueChange: (value: unknown) => void;
	errors: SchemaFormErrors;
};

export function SchemaFormInputArrayItem({
	items,
	value,
	onValueChange,
	errors,
}: SchemaFormInputArrayItemProps) {
	const { schema } = useSchemaFormContext();
	const id = useId();

	if (isArray(items)) {
		// @ts-expect-error The SchemaObject type requires a type property but in an anyOf property the type comes from the anyOf property
		const property: SchemaObject = {
			anyOf: items,
		};

		return (
			<SchemaFormInput
				value={value}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
				id={id}
			/>
		);
	}

	if (isReferenceObject(items)) {
		const property = getSchemaDefinition(schema, items.$ref);

		return (
			<SchemaFormInput
				value={value}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
				id={id}
			/>
		);
	}

	return (
		<SchemaFormInput
			value={value}
			onValueChange={onValueChange}
			property={items}
			errors={errors}
			id={id}
		/>
	);
}
