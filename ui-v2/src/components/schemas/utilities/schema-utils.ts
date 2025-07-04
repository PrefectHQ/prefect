import type { ReferenceObject, SchemaObject } from "openapi-typescript";

/**
 * Checks if a schema is a reference object
 */
export function isReferenceObject(
	schema: SchemaObject | ReferenceObject,
): schema is ReferenceObject {
	return "$ref" in schema;
}

/**
 * Checks if a schema is an object type schema
 */
export function isObjectSchema(
	schema: SchemaObject | ReferenceObject,
): schema is SchemaObject {
	return "type" in schema && schema.type === "object";
}

/**
 * Checks if a schema has properties defined
 */
export function hasProperties(
	schema: SchemaObject,
): schema is SchemaObject & { properties: Record<string, unknown> } {
	return "properties" in schema && schema.properties !== undefined;
}

/**
 * Extracts parameter values from a value object based on schema properties
 */
export function getParameterValues(
	value: unknown,
	schema: SchemaObject | ReferenceObject,
): unknown {
	if (isReferenceObject(schema)) {
		return value;
	}

	if (!isObjectSchema(schema) || !hasProperties(schema)) {
		return value;
	}

	const obj = value as Record<string, unknown>;
	const result: Record<string, unknown> = {};

	for (const [key] of Object.entries(schema.properties)) {
		if (key in obj) {
			result[key] = obj[key];
		}
	}

	return result;
}
