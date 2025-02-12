import { isDate } from "date-fns";

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
