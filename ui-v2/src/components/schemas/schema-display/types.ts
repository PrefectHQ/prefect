export interface JSONSchema {
	type?: string;
	properties?: Record<string, SchemaProperty>;
	default?: unknown;
	title?: string;
	description?: string;
	items?: SchemaProperty;
}

export interface SchemaProperty {
	type?: string;
	default?: unknown;
	title?: string;
	description?: string;
	properties?: Record<string, SchemaProperty>;
	items?: SchemaProperty;
	enum?: unknown[];
}

export type PropertyType =
	| "string"
	| "number"
	| "integer"
	| "boolean"
	| "object"
	| "array"
	| "null"
	| "unknown";

export interface PropertyRendererProps {
	property: SchemaProperty;
	value: unknown;
	path: string;
	name: string;
}
