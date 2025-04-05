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
	schema: SchemaObject | ReferenceObject,
): schema is SchemaWithDefinitions {
	return "definitions" in schema && isRecord(schema.definitions);
}

export function getSchemaDefinition(
	schema: SchemaObject | ReferenceObject,
	definition: string,
): SchemaObject {
	if (!isSchemaWithDefinitions(schema)) {
		throw new Error("Schema does not contain definitions");
	}

	const definitionKey = definition.replace("#/definitions/", "");
	const definitionSchema = schema.definitions?.[definitionKey];

	if (!definitionSchema) {
		throw new Error(`Definition not found for ${definition}`);
	}

	return definitionSchema;
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
