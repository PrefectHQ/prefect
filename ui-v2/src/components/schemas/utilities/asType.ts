import type { PrimitiveProperty } from "../types/primitives";
import { isRecord } from "./guards";

type PrimitiveConstructor =
	| BooleanConstructor
	| NumberConstructor
	| StringConstructor;

export function asType<T extends PrimitiveConstructor>(
	value: unknown,
	type: T,
): ReturnType<T> | undefined {
	if (typeof value === typeof type()) {
		return value as ReturnType<T>;
	}

	return undefined;
}

export function asObject(value: unknown): Record<string, unknown> | undefined {
	if (isRecord(value)) {
		return value;
	}

	return undefined;
}

export function asPrimitive(value: unknown): PrimitiveProperty | undefined {
	return (
		asType(value, String) ?? asType(value, Number) ?? asType(value, Boolean)
	);
}

export function asArray(value: unknown): unknown[] | undefined;
export function asArray(
	value: unknown,
	type: BooleanConstructor,
): boolean[] | undefined;
export function asArray(
	value: unknown,
	type: NumberConstructor,
): number[] | undefined;
export function asArray(
	value: unknown,
	type: StringConstructor,
): string[] | undefined;
export function asArray(
	value: unknown,
	type: "primitive",
): PrimitiveProperty[] | undefined;
export function asArray(
	value: unknown,
	type?: "primitive" | PrimitiveConstructor,
): unknown[] | undefined {
	if (type === undefined && Array.isArray(value)) {
		return value as unknown[];
	}

	if (!Array.isArray(value)) {
		return undefined;
	}

	switch (type) {
		case String:
			return value
				.map((value) => asType(value, String))
				.filter((value) => value !== undefined);
		case Number:
			return value
				.map((value) => asType(value, Number))
				.filter((value) => value !== undefined);
		case Boolean:
			return value
				.map((value) => asType(value, Boolean))
				.filter((value) => value !== undefined);
		case "primitive":
			return value
				.map(
					(value) =>
						asType(value, String) ??
						asType(value, Number) ??
						asType(value, Boolean),
				)
				.filter((value) => value !== undefined);
		default:
			// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
			throw new Error(`Invalid array type: ${type}`);
	}
}
