import type { SchemaObject } from "openapi-typescript";

type SchemaWithBlockTypeSlug = SchemaObject & {
	block_type_slug?: string;
	blockTypeSlug?: string;
	definitions?: Record<string, SchemaWithBlockTypeSlug>;
	properties?: Record<string, SchemaWithBlockTypeSlug>;
	anyOf?: SchemaWithBlockTypeSlug[];
	allOf?: SchemaWithBlockTypeSlug[];
	oneOf?: SchemaWithBlockTypeSlug[];
	items?: SchemaWithBlockTypeSlug | SchemaWithBlockTypeSlug[];
};

/**
 * Recursively enriches a schema by converting `block_type_slug` to `blockTypeSlug`.
 * This is needed because the API returns snake_case but the UI expects camelCase.
 *
 * When a property has `block_type_slug`, the schema form will render a block document
 * selector (dropdown + "Add" button) instead of showing all the fields inline.
 */
export function enrichSchemaWithBlockTypeSlug<T extends SchemaObject>(
	schema: T,
): T {
	if (!schema || typeof schema !== "object") {
		return schema;
	}

	const result = { ...schema } as SchemaWithBlockTypeSlug;

	if (
		"block_type_slug" in result &&
		typeof result.block_type_slug === "string"
	) {
		result.blockTypeSlug = result.block_type_slug;
	}

	if (result.definitions) {
		result.definitions = Object.fromEntries(
			Object.entries(result.definitions).map(([key, value]) => [
				key,
				enrichSchemaWithBlockTypeSlug(value),
			]),
		);
	}

	if (result.properties) {
		result.properties = Object.fromEntries(
			Object.entries(result.properties).map(([key, value]) => [
				key,
				enrichSchemaWithBlockTypeSlug(value),
			]),
		);
	}

	if (result.anyOf) {
		result.anyOf = result.anyOf.map((item) =>
			enrichSchemaWithBlockTypeSlug(item),
		);
	}

	if (result.allOf) {
		result.allOf = result.allOf.map((item) =>
			enrichSchemaWithBlockTypeSlug(item),
		);
	}

	if (result.oneOf) {
		result.oneOf = result.oneOf.map((item) =>
			enrichSchemaWithBlockTypeSlug(item),
		);
	}

	if (result.items) {
		if (Array.isArray(result.items)) {
			result.items = result.items.map((item) =>
				enrichSchemaWithBlockTypeSlug(item),
			);
		} else {
			result.items = enrichSchemaWithBlockTypeSlug(result.items);
		}
	}

	return result as T;
}
