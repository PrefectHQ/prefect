import merge from "lodash.merge";
import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useMemo } from "react";
import { SchemaFormInput } from "./schema-form-input";
import type { SchemaFormErrors } from "./types/errors";
import { useSchemaFormContext } from "./use-schema-form-context";
import { isReferenceObject } from "./utilities/guards";
import { getSchemaDefinition } from "./utilities/mergeSchemaPropertyDefinition";

export type SchemaFormInputAllOfProps = {
	property: SchemaObject & { allOf: (SchemaObject | ReferenceObject)[] };
	value: unknown;
	onValueChange: (value: unknown) => void;
	errors: SchemaFormErrors;
	id: string;
};

export function SchemaFormInputAllOf({
	property,
	value,
	onValueChange,
	errors,
	id,
}: SchemaFormInputAllOfProps) {
	const { schema } = useSchemaFormContext();

	const merged = useMemo(() => {
		const { allOf, ...baseProperty } = property;

		const definitions = allOf.reduce((property, definition) => {
			if (isReferenceObject(definition)) {
				const reference = getSchemaDefinition(schema, definition.$ref);

				return merge({}, property, reference);
			}

			return merge({}, property, definition);
		}, {});

		return merge({}, definitions, baseProperty);
	}, [property, schema]);

	return (
		<SchemaFormInput
			value={value}
			onValueChange={onValueChange}
			errors={errors}
			property={merged}
			id={id}
		/>
	);
}
