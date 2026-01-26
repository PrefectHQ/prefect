import type { PrefectSchemaObject } from "../types/schemas";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySchema = Record<string, any>;

/**
 * Recursively enriches a schema by converting `block_type_slug` to `blockTypeSlug`.
 * This is needed because the API returns snake_case but the UI expects camelCase.
 *
 * When a property has `block_type_slug`, the schema form will render a block document
 * selector (dropdown + "Add" button) instead of showing all the fields inline.
 */
export function enrichSchemaWithBlockTypeSlug(
	schema: PrefectSchemaObject,
): PrefectSchemaObject {
	return enrichSchemaRecursive(schema) as PrefectSchemaObject;
}

function enrichSchemaRecursive(schema: AnySchema): AnySchema {
	if (!schema || typeof schema !== "object") {
		return schema;
	}

	const result: AnySchema = { ...schema };

	if (
		"block_type_slug" in result &&
		typeof result.block_type_slug === "string"
	) {
		result.blockTypeSlug = result.block_type_slug;
	}

	if (result.definitions && typeof result.definitions === "object") {
		result.definitions = Object.fromEntries(
			Object.entries(result.definitions as AnySchema).map(([key, value]) => [
				key,
				enrichSchemaRecursive(value as AnySchema),
			]),
		);
	}

	if (result.properties && typeof result.properties === "object") {
		result.properties = Object.fromEntries(
			Object.entries(result.properties as AnySchema).map(([key, value]) => [
				key,
				enrichSchemaRecursive(value as AnySchema),
			]),
		);
	}

	if (Array.isArray(result.anyOf)) {
		result.anyOf = result.anyOf.map((item: AnySchema) =>
			enrichSchemaRecursive(item),
		);
	}

	if (Array.isArray(result.allOf)) {
		result.allOf = result.allOf.map((item: AnySchema) =>
			enrichSchemaRecursive(item),
		);
	}

	if (Array.isArray(result.oneOf)) {
		result.oneOf = result.oneOf.map((item: AnySchema) =>
			enrichSchemaRecursive(item),
		);
	}

	if (result.items) {
		if (Array.isArray(result.items)) {
			result.items = result.items.map((item: AnySchema) =>
				enrichSchemaRecursive(item),
			);
		} else {
			result.items = enrichSchemaRecursive(result.items as AnySchema);
		}
	}

	return result;
}
