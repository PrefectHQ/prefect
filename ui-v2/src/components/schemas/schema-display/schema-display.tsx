import { cn } from "@/utils";

import { ArrayProperty } from "./property-types/array-property";
import { BooleanProperty } from "./property-types/boolean-property";
import { NumberProperty } from "./property-types/number-property";
import { ObjectProperty } from "./property-types/object-property";
import { StringProperty } from "./property-types/string-property";

export type JSONSchema = {
	type?: string;
	properties?: Record<string, SchemaProperty>;
	default?: unknown;
	title?: string;
	description?: string;
	items?: SchemaProperty;
};

export type SchemaProperty = {
	type?: string;
	default?: unknown;
	title?: string;
	description?: string;
	properties?: Record<string, SchemaProperty>;
	items?: SchemaProperty;
	enum?: unknown[];
};

export type PropertyType =
	| "string"
	| "number"
	| "integer"
	| "boolean"
	| "object"
	| "array"
	| "null"
	| "unknown";

export type PropertyRendererProps = {
	property: SchemaProperty;
	value: unknown;
	path: string;
	name: string;
};

export type SchemaDisplayProps = {
	schema: JSONSchema;
	data: Record<string, unknown>;
	className?: string;
};

function getPropertyDisplayName(key: string, property: SchemaProperty): string {
	return (
		property.title ||
		key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
	);
}

function getPropertyType(property: SchemaProperty): PropertyType {
	if (!property.type) return "unknown";

	switch (property.type) {
		case "string":
			return "string";
		case "number":
		case "integer":
			return "number";
		case "boolean":
			return "boolean";
		case "object":
			return "object";
		case "array":
			return "array";
		case "null":
			return "null";
		default:
			return "unknown";
	}
}

function PropertyRenderer({
	property,
	value,
	path,
	name,
}: {
	property: SchemaProperty;
	value: unknown;
	path: string;
	name: string;
}) {
	const type = getPropertyType(property);

	const commonProps = { property, value, path, name };

	switch (type) {
		case "string":
			return <StringProperty {...commonProps} />;
		case "number":
			return <NumberProperty {...commonProps} />;
		case "boolean":
			return <BooleanProperty {...commonProps} />;
		case "object":
			return <ObjectProperty {...commonProps} />;
		case "array":
			return <ArrayProperty {...commonProps} />;
		case "null":
			return (
				<span className="font-mono text-sm text-muted-foreground">null</span>
			);
		default:
			return (
				<pre className="text-xs font-mono">
					{JSON.stringify(value, null, 2)}
				</pre>
			);
	}
}

export function SchemaDisplay({ schema, data, className }: SchemaDisplayProps) {
	if (!schema.properties) {
		return (
			<div className={cn("text-sm text-muted-foreground", className)}>
				No properties defined
			</div>
		);
	}

	const properties = Object.entries(schema.properties);

	if (properties.length === 0) {
		return (
			<div className={cn("text-sm text-muted-foreground", className)}>
				No properties to display
			</div>
		);
	}

	return (
		<div className={cn("space-y-4", className)}>
			{properties.map(([key, property]) => {
				const displayName = getPropertyDisplayName(key, property);
				const value = data[key];

				return (
					<div key={key} className="space-y-2">
						<div className="flex items-start justify-between">
							<div className="space-y-1">
								<dt className="text-sm font-medium">{displayName}</dt>
								{property.description && (
									<p className="text-xs text-muted-foreground">
										{property.description}
									</p>
								)}
							</div>
						</div>
						<dd className="mt-1">
							<PropertyRenderer
								property={property}
								value={value}
								path={key}
								name={displayName}
							/>
						</dd>
					</div>
				);
			})}
		</div>
	);
}
