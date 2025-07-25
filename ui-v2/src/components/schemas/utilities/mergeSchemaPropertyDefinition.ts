import merge from "lodash.merge";
import type {
	ObjectSubtype,
	ReferenceObject,
	SchemaObject,
} from "openapi-typescript";
import { isRecord, isReferenceObject } from "./guards";

type SchemaWithDefinitions = SchemaObject &
	ObjectSubtype & {
		definitions: Record<string, SchemaObject>;
	};

function isSchemaWithDefinitions(
	schema: SchemaObject | ReferenceObject | ObjectSubtype,
): schema is SchemaWithDefinitions {
	return "definitions" in schema && isRecord(schema.definitions);
}

export function getSchemaDefinition(
	schema: SchemaObject | ReferenceObject | ObjectSubtype,
	definition: string,
): SchemaObject {
	if (isSchemaWithDefinitions(schema)) {
		const definitionKey = definition.replace("#/definitions/", "");
		const definitionSchema = schema.definitions?.[definitionKey];

		if (!definitionSchema) {
			throw new Error(`Definition not found for ${definition}`);
		}

		return definitionSchema;
	}
	if ("$defs" in schema && isRecord(schema.$defs)) {
		const definitionKey = definition.replace("#/$defs/", "");
		const definitionSchema = schema.$defs?.[definitionKey];
		if (!definitionSchema) {
			throw new Error(`Definition not found for ${definition}`);
		}

		return definitionSchema;
	}

	throw new Error("Schema does not contain definitions");
}

export function mergeSchemaPropertyDefinition(
	property: SchemaObject | ReferenceObject,
	schema: SchemaObject & ObjectSubtype,
): SchemaObject {
	if (isReferenceObject(property) && typeof property.$ref === "string") {
		const { $ref, ...rest } = property;

		return merge({}, getSchemaDefinition(schema, $ref), rest);
	}

	return property as SchemaObject;
}
