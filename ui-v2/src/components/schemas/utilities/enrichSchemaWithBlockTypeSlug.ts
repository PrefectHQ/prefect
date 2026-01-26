import type { PrefectSchemaObject } from "../types/schemas";

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
	if (!schema || typeof schema !== "object") {
		return schema;
	}

	// Use a generic record type for mutation, then cast back
	const result: Record<string, unknown> = { ...schema };

	if (
		"block_type_slug" in result &&
		typeof result.block_type_slug === "string"
	) {
		result.blockTypeSlug = result.block_type_slug;
	}

	if (result.definitions && typeof result.definitions === "object") {
		result.definitions = Object.fromEntries(
			Object.entries(
				result.definitions as Record<string, PrefectSchemaObject>,
			).map(([key, value]) => [key, enrichSchemaWithBlockTypeSlug(value)]),
		);
	}

	if (result.properties && typeof result.properties === "object") {
		result.properties = Object.fromEntries(
			Object.entries(
				result.properties as Record<string, PrefectSchemaObject>,
			).map(([key, value]) => [key, enrichSchemaWithBlockTypeSlug(value)]),
		);
	}

	if (Array.isArray(result.anyOf)) {
		result.anyOf = result.anyOf.map((item: PrefectSchemaObject) =>
			enrichSchemaWithBlockTypeSlug(item),
		);
	}

	if (Array.isArray(result.allOf)) {
		result.allOf = result.allOf.map((item: PrefectSchemaObject) =>
			enrichSchemaWithBlockTypeSlug(item),
		);
	}

	if (Array.isArray(result.oneOf)) {
		result.oneOf = result.oneOf.map((item: PrefectSchemaObject) =>
			enrichSchemaWithBlockTypeSlug(item),
		);
	}

	if (result.items) {
		if (Array.isArray(result.items)) {
			result.items = result.items.map((item: PrefectSchemaObject) =>
				enrichSchemaWithBlockTypeSlug(item),
			);
		} else {
			result.items = enrichSchemaWithBlockTypeSlug(
				result.items as PrefectSchemaObject,
			);
		}
	}

	return result as PrefectSchemaObject;
}
