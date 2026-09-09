import merge from "lodash.merge";
import type {
	ObjectSubtype,
	ReferenceObject,
	SchemaObject,
} from "openapi-typescript";
import { isRecord, isReferenceObject } from "./guards";

const DEFINITION_CONTAINERS = ["definitions", "$defs"] as const;

type DefinitionContainer = (typeof DEFINITION_CONTAINERS)[number];

function parseDefinitionReference(definition: string): {
	container: DefinitionContainer | undefined;
	key: string;
} {
	for (const container of DEFINITION_CONTAINERS) {
		const prefix = `#/${container}/`;

		if (definition.startsWith(prefix)) {
			return { container, key: definition.slice(prefix.length) };
		}
	}

	return { container: undefined, key: definition };
}

function getDefinitionContainers(
	schema: SchemaObject | ReferenceObject | ObjectSubtype,
	preferred: DefinitionContainer | undefined,
): Record<string, unknown>[] {
	const record: Record<string, unknown> = { ...schema };
	const order = preferred
		? [preferred, ...DEFINITION_CONTAINERS.filter((key) => key !== preferred)]
		: [...DEFINITION_CONTAINERS];

	return order.flatMap((key) => {
		const container = record[key];
		return isRecord(container) ? [container] : [];
	});
}

/**
 * Resolves a `$ref` such as `#/definitions/Foo` or `#/$defs/Foo` against the
 * root schema. Pydantic emits `$defs` while Prefect rewrites refs to
 * `#/definitions/`, so schemas in the wild mix the two. The container named in
 * the ref is checked first and the other container is used as a fallback.
 */
export function getSchemaDefinition(
	schema: SchemaObject | ReferenceObject | ObjectSubtype,
	definition: string,
): SchemaObject {
	const { container: preferred, key: definitionKey } =
		parseDefinitionReference(definition);
	const containers = getDefinitionContainers(schema, preferred);

	if (containers.length === 0) {
		return {} as SchemaObject;
	}

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
