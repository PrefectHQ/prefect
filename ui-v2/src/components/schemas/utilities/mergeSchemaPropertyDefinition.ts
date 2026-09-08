import merge from "lodash.merge";
import type {
	ObjectSubtype,
	ReferenceObject,
	SchemaObject,
} from "openapi-typescript";
import { isRecord, isReferenceObject } from "./guards";

const DEFINITION_CONTAINERS = ["definitions", "$defs"] as const;

function getDefinitionContainers(
	schema: SchemaObject | ReferenceObject | ObjectSubtype,
): Record<string, unknown>[] {
	const record: Record<string, unknown> = { ...schema };

	return DEFINITION_CONTAINERS.flatMap((key) => {
		const container = record[key];
		return isRecord(container) ? [container] : [];
	});
}

/**
 * Resolves a `$ref` such as `#/definitions/Foo` or `#/$defs/Foo` against the
 * root schema. Pydantic emits `$defs` while Prefect rewrites refs to
 * `#/definitions/`, so schemas in the wild mix the two; the lookup uses the
 * definition name and checks both containers.
 */
export function getSchemaDefinition(
	schema: SchemaObject | ReferenceObject | ObjectSubtype,
	definition: string,
): SchemaObject {
	const containers = getDefinitionContainers(schema);

	if (containers.length === 0) {
		return {} as SchemaObject;
	}

	const definitionKey = definition
		.replace("#/definitions/", "")
		.replace("#/$defs/", "");

	for (const container of containers) {
		const definitionSchema = container[definitionKey];

		if (isRecord(definitionSchema)) {
			return definitionSchema as SchemaObject;
		}
	}

	throw new Error(`Definition not found for ${definition}`);
}

export function mergeSchemaPropertyDefinition(
	property: SchemaObject | ReferenceObject,
	schema: SchemaObject,
): SchemaObject {
	if (isReferenceObject(property) && typeof property.$ref === "string") {
		const { $ref, ...rest } = property;

		return merge({}, getSchemaDefinition(schema, $ref), rest);
	}

	return property as SchemaObject;
}
