import type {
	ArraySubtype,
	ObjectSubtype,
	ReferenceObject,
	SchemaObject,
} from "openapi-typescript";
import type { PrefectKind } from "../types/prefect-kind";
import type {
	PrefectKindValueJinja,
	PrefectKindValueJson,
} from "../types/prefect-kind-value";
import { getPrefectKindFromValue } from "../types/prefect-kind-value";
import { isAnyOfObject, isArray, isRecord } from "./guards";
import { mergeSchemaPropertyDefinition } from "./mergeSchemaPropertyDefinition";

type ConvertValueToPrefectKindInput = {
	value: unknown;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	schema: SchemaObject & ObjectSubtype;
	to: PrefectKind;
};

export function convertValueToPrefectKind({
	value,
	property,
	schema,
	to,
}: ConvertValueToPrefectKindInput) {
	const from = getPrefectKindFromValue(value);

	try {
		switch (from) {
			case "json":
				return convertPrefectKindValueJson({
					json: value as PrefectKindValueJson,
					property,
					schema,
					to,
				});

			case "jinja":
				return convertPrefectKindValueJinja({
					jinja: value as PrefectKindValueJinja,
					property,
					schema,
					to,
				});

			case null:
				return convertPrefectKindValueNull({ value, property, schema, to });

			default:
				// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
				throw new Error(`Unknown prefect kind value: ${from satisfies never}`);
		}
	} catch (error) {
		console.error(error);

		return undefined;
	}
}

type ConvertPrefectKindValueJsonInput = {
	json: PrefectKindValueJson;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	schema: SchemaObject & ObjectSubtype;
	to: PrefectKind;
};

function convertPrefectKindValueJson({
	json,
	property,
	schema,
	to,
}: ConvertPrefectKindValueJsonInput): unknown {
	switch (to) {
		case "jinja":
			return {
				__prefect_kind: "jinja",
				template: json.value,
			} satisfies PrefectKindValueJinja;

		case "json":
			return json;

		case null:
			if (json.value === undefined) {
				return undefined;
			}

			try {
				const parsed: unknown = JSON.parse(json.value);

				return coerceValueToProperties({ value: parsed, property, schema });
			} catch {
				throw new InvalidSchemaValueTransformation("json", null);
			}

		default:
			throw new Error(
				// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
				`mapSchemaValueJson missing case for kind: ${to satisfies never}`,
			);
	}
}

type ConvertPrefectKindValueJinjaInput = {
	jinja: PrefectKindValueJinja;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	schema: SchemaObject & ObjectSubtype;
	to: PrefectKind;
};

function convertPrefectKindValueJinja({
	jinja,
	property,
	schema,
	to,
}: ConvertPrefectKindValueJinjaInput): unknown {
	switch (to) {
		case "jinja":
			return jinja;

		case "json":
			return {
				__prefect_kind: "json",
				value: jinja.template,
			} satisfies PrefectKindValueJson;

		case null:
			if (jinja.template === undefined) {
				return undefined;
			}

			try {
				const parsed: unknown = JSON.parse(jinja.template);

				return coerceValueToProperties({ value: parsed, property, schema });
			} catch {
				throw new InvalidSchemaValueTransformation("jinja", null);
			}

		default:
			throw new Error(
				// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
				`mapSchemaValueJson missing case for kind: ${to satisfies never}`,
			);
	}
}

type ConvertPrefectKindValueNullInput = {
	value: unknown;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	schema: SchemaObject & ObjectSubtype;
	to: PrefectKind;
};

function convertPrefectKindValueNull({
	value,
	property,
	schema,
	to,
}: ConvertPrefectKindValueNullInput): unknown {
	switch (to) {
		case "jinja":
			return {
				__prefect_kind: "jinja",
				template:
					value === undefined ? undefined : JSON.stringify(value, null, 2),
			} satisfies PrefectKindValueJinja;

		case "json":
			return {
				__prefect_kind: "json",
				value: value === undefined ? undefined : JSON.stringify(value, null, 2),
			} satisfies PrefectKindValueJson;

		case null:
			return coerceValueToProperties({ value, property, schema });

		default:
			throw new Error(
				// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
				`mapSchemaValueJson missing case for kind: ${to satisfies never}`,
			);
	}
}

type CoerceValueToPropertiesInput = {
	value: unknown;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	schema: SchemaObject & ObjectSubtype;
};

function coerceValueToProperties({
	value,
	property,
	schema,
}: CoerceValueToPropertiesInput): unknown {
	if (isArray(property)) {
		const responses = property.map((property) =>
			coerceValueToProperty({ value, property, schema }),
		);

		return responses.find((response) => response !== undefined);
	}

	return coerceValueToProperty({ value, property, schema });
}

type CoerceValueToPropertyInput = {
	value: unknown;
	property: SchemaObject | ReferenceObject;
	schema: SchemaObject & ObjectSubtype;
};

function coerceValueToProperty({
	value,
	property,
	schema,
}: CoerceValueToPropertyInput): unknown {
	const merged = mergeSchemaPropertyDefinition(property, schema);

	if (isAnyOfObject(merged)) {
		return coerceValueToProperties({ value, property: merged.anyOf, schema });
	}

	switch (merged.type) {
		case "null":
			return null;

		case "string":
			return typeof value === "string" ? value : undefined;

		case "boolean":
			return typeof value === "boolean" ? value : undefined;

		case "number":
			return typeof value === "number" ? value : undefined;

		case "integer":
			return typeof value === "number" ? Math.round(value) : undefined;

		case "array":
			return coerceValueToArrayProperty({ value, property: merged, schema });

		case "object":
			return coerceValueToObjectProperty({ value, property: merged, schema });

		default:
			if (isArray(merged.type)) {
				console.error(
					new Error(
						"Array types are not supported for schema coercing values to schema properties",
					),
				);

				return undefined;
			}

			throw new Error(
				// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
				`Unsupported property type: ${merged.type satisfies never}`,
			);
	}
}

type CoerceValueToArrayPropertyInput = {
	value: unknown;
	property: SchemaObject & ArraySubtype;
	schema: SchemaObject & ObjectSubtype;
};

function coerceValueToArrayProperty({
	value,
	property,
	schema,
}: CoerceValueToArrayPropertyInput): unknown[] | undefined {
	if (!isArray(value)) {
		return undefined;
	}

	const response = [...value];

	return response.map((item) =>
		coerceValueToProperty({ value: item, property, schema }),
	);
}

type CoerceValueToObjectPropertyInput = {
	value: unknown;
	property: SchemaObject & ObjectSubtype;
	schema: SchemaObject & ObjectSubtype;
};

function coerceValueToObjectProperty({
	value,
	property,
	schema,
}: CoerceValueToObjectPropertyInput): Record<string, unknown> | undefined {
	if (!isRecord(value)) {
		return undefined;
	}

	if (property.properties === undefined) {
		return value;
	}

	const response = { ...value };

	for (const [key, propertyValue] of Object.entries(property.properties)) {
		const coercedValue = coerceValueToProperty({
			value: value[key],
			property: propertyValue,
			schema,
		});

		if (coercedValue === undefined) {
			delete response[key];
		}
	}

	return response;
}

class InvalidSchemaValueTransformation extends Error {
	public constructor(from: PrefectKind, to: PrefectKind | null) {
		super(
			`Unable to convert prefect kind value from "${from}" to "${to ?? "null"}"`,
		);
	}
}
