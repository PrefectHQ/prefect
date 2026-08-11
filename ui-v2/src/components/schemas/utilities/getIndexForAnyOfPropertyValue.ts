import type { SchemaObject } from "openapi-typescript";
import { isPrefectKindValue } from "../types/prefect-kind-value";
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
 * @returns The index of the definition that matches the value, or 0 when no
 * definition matches
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
	const index = getMatchingDefinitionIndex(valueOrDefaultValue, definitions);

	// values that don't match any definition default to showing the first one
	return index >= 0 ? index : 0;
}

/**
 * Get the index of the definition that matches a defined value
 * @param valueOrDefaultValue - The value to match
 * @param definitions - The definitions to match
 * @returns The index of the definition that matches the value, or -1 when no
 * definition matches
 */
function getMatchingDefinitionIndex(
	valueOrDefaultValue: unknown,
	definitions: SchemaObject[],
): number {
	if (isPrefectKindValue(valueOrDefaultValue)) {
		return definitions.findIndex((definition) => !isDefined(definition.type));
	}

	switch (typeof valueOrDefaultValue) {
		case "string":
			return getPrimitiveDefinitionIndex(
				valueOrDefaultValue,
				definitions,
				(definition) => definition.type === "string",
			);
		case "number":
			return getPrimitiveDefinitionIndex(
				valueOrDefaultValue,
				definitions,
				(definition) =>
					definition.type === "number" || definition.type === "integer",
			);
		case "boolean":
			return getPrimitiveDefinitionIndex(
				valueOrDefaultValue,
				definitions,
				(definition) => definition.type === "boolean",
			);
		case "object":
			return getObjectDefinitionIndex(valueOrDefaultValue, definitions);
		default:
			return -1;
	}
}

/**
 * Get the index of the definition that matches a primitive value, preferring an
 * enum definition that includes the value over a definition without an enum.
 * Enum definitions without a type, like referenced python enums, are eligible.
 * @param value - The value to match
 * @param definitions - The definitions to match
 * @param matchesType - Whether a definition has the same type as the value
 * @returns The index of the definition that matches the value
 */
function getPrimitiveDefinitionIndex(
	value: string | number | boolean,
	definitions: SchemaObject[],
	matchesType: (definition: SchemaObject) => boolean,
): number {
	const enumIndex = definitions.findIndex(
		(definition) =>
			(matchesType(definition) || !isDefined(definition.type)) &&
			isArray(definition.enum) &&
			definition.enum.includes(value),
	);

	if (enumIndex >= 0) {
		return enumIndex;
	}

	const nonEnumIndex = definitions.findIndex(
		(definition) => matchesType(definition) && !isDefined(definition.enum),
	);

	if (nonEnumIndex >= 0) {
		return nonEnumIndex;
	}

	return definitions.findIndex(matchesType);
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

	// definitions that don't declare properties, like an untyped `dict`, can
	// hold any record value, so they're preferred over a structured definition
	// the value shares no keys with
	if (keysInCommon === 0) {
		const openObjectIndex = definitions.findIndex(
			(definition) =>
				definition.type === "object" &&
				(!("properties" in definition) || !definition.properties),
		);

		if (openObjectIndex >= 0) {
			return openObjectIndex;
		}

		return definitions.findIndex((definition) => definition.type === "object");
	}

	return index;
}
