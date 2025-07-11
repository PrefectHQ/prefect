import type { SchemaObject } from "openapi-typescript";
import {
	isArray,
	isDefined,
	isEmptyObject,
	isRecord,
	isReferenceObject,
} from "./guards";
import { getSchemaDefinition } from "./mergeSchemaPropertyDefinition";

type InitialIndexContext = {
	property: SchemaObject;
	value: unknown;
	schema: SchemaObject;
};

/**
 * Get the index of the definition that matches the value
 * @param value - The value to match
 * @param property - The property to match
 * @param schema - The schema to match
 * @returns The index of the definition that matches the value
 */
export function getIndexForAnyOfPropertyValue({
	value,
	property,
	schema,
}: InitialIndexContext): number {
	const valueOrDefaultValue = isDefined(value) ? value : property.default;

	// if there's no value default to showing the first definition
	if (!isDefined(valueOrDefaultValue)) {
		return 0;
	}

	const definitions = getSchemaPropertyAnyOfDefinitions(property, schema);

	switch (typeof valueOrDefaultValue) {
		case "string":
			return definitions.findIndex(
				(definition) => definition.type === "string",
			);
		case "number":
			return definitions.findIndex(
				(definition) =>
					definition.type === "number" || definition.type === "integer",
			);
		case "boolean":
			return definitions.findIndex(
				(definition) => definition.type === "boolean",
			);
		case "object":
			return getObjectDefinitionIndex(valueOrDefaultValue, definitions);
		default:
			return -1;
	}
}

/**
 * Get the definitions for the anyOf property
 * @param property - The property to get the definitions for
 * @param schema - The schema to get the definitions for
 * @returns The definitions for the anyOf property
 */
function getSchemaPropertyAnyOfDefinitions(
	property: SchemaObject,
	schema: SchemaObject,
): SchemaObject[] {
	if (!property.anyOf) {
		return [];
	}

	return property.anyOf.map((definition) => {
		if (isReferenceObject(definition)) {
			return getSchemaDefinition(schema, definition.$ref);
		}

		return definition;
	});
}

/**
 * Get the index of the definition that matches a value that is an array, record, or null
 * @param value - The value to match
 * @param definitions - The definitions to match
 * @returns The index of the definition that matches the value
 */
function getObjectDefinitionIndex(
	value: object | null,
	definitions: SchemaObject[],
): number {
	if (isRecord(value)) {
		return getRecordDefinitionIndex(value, definitions);
	}

	if (isArray(value)) {
		return definitions.findIndex((definition) => definition.type === "array");
	}

	if (value === null) {
		return definitions.findIndex((definition) => definition.type === "null");
	}

	return -1;
}

/**
 * Get the index of the definition that matches a value that is an record
 * @param value - The value to match
 * @param definitions - The definitions to match
 * @returns The index of the definition that matches the value
 */
function getRecordDefinitionIndex(
	value: Record<string, unknown>,
	definitions: SchemaObject[],
): number {
	if (isEmptyObject(value)) {
		return definitions.findIndex((definition) => definition.type === "object");
	}

	const valueKeys = Object.keys(value);

	const [index, keysInCommon] = definitions.reduce<[number, number]>(
		([resultIndex, resultKeysInCommon], definition, definitionIndex) => {
			if (!("properties" in definition) || !definition.properties) {
				return [resultIndex, resultKeysInCommon];
			}

			const definitionKeys = Object.keys(definition.properties);
			const definitionKeysInCommon = valueKeys.filter((value) =>
				definitionKeys.includes(value),
			).length;

			if (definitionKeysInCommon > resultKeysInCommon) {
				return [definitionIndex, definitionKeysInCommon];
			}

			return [resultIndex, resultKeysInCommon];
		},
		[0, 0],
	);

	if (keysInCommon === 0) {
		return -1;
	}

	return index;
}
