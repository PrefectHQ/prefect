import { isDate } from "date-fns";
import type { ReferenceObject, SchemaObject } from "openapi-typescript";

export function isString(value: unknown): value is string {
	return typeof value === "string";
}

export function isDefined<T>(value: T | undefined): value is T {
	return value !== undefined;
}

export function isRecord(item: unknown): item is Record<PropertyKey, unknown> {
	return (
		item !== null &&
		typeof item === "object" &&
		!Array.isArray(item) &&
		!isDate(item)
	);
}

export function isArray(item: unknown): item is unknown[] {
	return Array.isArray(item);
}

export function isEmptyObject(value: unknown): value is Record<string, never> {
	return (
		typeof value === "object" &&
		!Array.isArray(value) &&
		value !== null &&
		Object.keys(value).length === 0
	);
}

export function isReferenceObject(
	property: SchemaObject | ReferenceObject,
): property is ReferenceObject {
	return "$ref" in property;
}

export function isAnyOfObject(
	property: SchemaObject,
): property is SchemaObject & { anyOf: (SchemaObject | ReferenceObject)[] } {
	return "anyOf" in property && isDefined(property.anyOf);
}

export function isOneOfObject(
	property: SchemaObject,
): property is SchemaObject & { oneOf: (SchemaObject | ReferenceObject)[] } {
	return "oneOf" in property && isDefined(property.oneOf);
}

export function isAllOfObject(
	property: SchemaObject,
): property is SchemaObject & { allOf: (SchemaObject | ReferenceObject)[] } {
	return "allOf" in property && isDefined(property.allOf);
}

export function isItemsObject(
	property: SchemaObject,
): property is SchemaObject & {
	items: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
} {
	return "items" in property && isDefined(property.items);
}
