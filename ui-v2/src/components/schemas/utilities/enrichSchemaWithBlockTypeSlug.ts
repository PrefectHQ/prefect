/**
 * Type for schema objects that may contain block_type_slug from the API.
 * This is a loose type to handle the dynamic nature of JSON schemas.
 */
type SchemaLike = {
	[key: string]: unknown;
	block_type_slug?: string;
	blockTypeSlug?: string;
	definitions?: Record<string, SchemaLike>;
	properties?: Record<string, SchemaLike>;
	anyOf?: SchemaLike[];
	allOf?: SchemaLike[];
	oneOf?: SchemaLike[];
	items?: SchemaLike | SchemaLike[];
};

/**
 * Recursively enriches a schema by converting `block_type_slug` to `blockTypeSlug`.
 * This is needed because the API returns snake_case but the UI expects camelCase.
 *
 * When a property has `block_type_slug`, the schema form will render a block document
 * selector (dropdown + "Add" button) instead of showing all the fields inline.
 */
export function enrichSchemaWithBlockTypeSlug<T extends SchemaLike>(
	schema: T,
): T & { blockTypeSlug?: string } {
	if (!schema || typeof schema !== "object") {
		return schema as T & { blockTypeSlug?: string };
	}

	const result = { ...schema } as T & { blockTypeSlug?: string };

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
		) as T["definitions"];
	}

	if (result.properties) {
		result.properties = Object.fromEntries(
			Object.entries(result.properties).map(([key, value]) => [
				key,
				enrichSchemaWithBlockTypeSlug(value),
			]),
		) as T["properties"];
	}

	if (result.anyOf) {
		result.anyOf = result.anyOf.map((item) =>
			enrichSchemaWithBlockTypeSlug(item),
		) as T["anyOf"];
	}

	if (result.allOf) {
		result.allOf = result.allOf.map((item) =>
			enrichSchemaWithBlockTypeSlug(item),
		) as T["allOf"];
	}

	if (result.oneOf) {
		result.oneOf = result.oneOf.map((item) =>
			enrichSchemaWithBlockTypeSlug(item),
		) as T["oneOf"];
	}

	if (result.items) {
		if (Array.isArray(result.items)) {
			result.items = result.items.map((item) =>
				enrichSchemaWithBlockTypeSlug(item),
			) as T["items"];
		} else {
			result.items = enrichSchemaWithBlockTypeSlug(result.items) as T["items"];
		}
	}

	return result;
}
