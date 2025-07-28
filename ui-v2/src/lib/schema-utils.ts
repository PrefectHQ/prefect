import type {
	JSONSchema,
	SchemaProperty,
} from "@/components/schemas/schema-display";

/**
 * Extract default values from schema properties
 */
export function extractSchemaDefaults(
	schema: JSONSchema,
): Record<string, unknown> {
	const defaults: Record<string, unknown> = {};

	if (!schema.properties) {
		return defaults;
	}

	for (const [key, property] of Object.entries(schema.properties)) {
		if (property.default !== undefined) {
			defaults[key] = property.default;
		}
	}

	return defaults;
}

/**
 * Format property values based on property type
 */
export function formatPropertyValue(
	value: unknown,
	property: SchemaProperty,
): React.ReactNode {
	if (value === null || value === undefined) {
		return (property.default as React.ReactNode) || "—";
	}

	switch (property.type) {
		case "boolean":
			return typeof value === "boolean"
				? value.toString()
				: JSON.stringify(value);
		case "number":
		case "integer":
			return typeof value === "number"
				? value.toString()
				: JSON.stringify(value);
		case "string":
			return typeof value === "string" ? value : JSON.stringify(value);
		case "array":
			return Array.isArray(value)
				? `[${value.length} items]`
				: JSON.stringify(value);
		case "object":
			return typeof value === "object" && value !== null
				? `{${Object.keys(value).length} properties}`
				: JSON.stringify(value);
		default:
			return JSON.stringify(value);
	}
}

/**
 * Get display name for a property
 */
export function getPropertyDisplayName(
	key: string,
	property: SchemaProperty,
): string {
	return (
		property.title ||
		key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
	);
}

/**
 * Convert string to title case
 */
export function toTitleCase(str: string): string {
	return str.replace(
		/\w\S*/g,
		(txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase(),
	);
}
