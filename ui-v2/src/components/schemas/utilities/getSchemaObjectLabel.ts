import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { isReferenceObject } from "./guards";
import { getSchemaDefinition } from "./mergeSchemaPropertyDefinition";

const schemaObjectTypeLabels: Record<string, string | undefined> = {
	null: "None",
	string: "str",
	boolean: "bool",
	integer: "int",
	number: "float",
	array: "list",
	object: "dict",
};

function getSchemaObjectTypeLabel(property: SchemaObject): string | undefined {
	if (property.type && typeof property.type === "string") {
		return schemaObjectTypeLabels[property.type];
	}

	return undefined;
}

export function getSchemaObjectLabel(
	property: SchemaObject | ReferenceObject,
	schema: SchemaObject,
): string {
	if (isReferenceObject(property)) {
		const definition = getSchemaDefinition(schema, property.$ref);

		return getSchemaObjectLabel(definition, schema);
	}

	const fallback = getSchemaObjectTypeLabel(property) ?? "Field";

	return property.title ?? property.format ?? fallback;
}
