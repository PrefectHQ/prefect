import type { MaybeGetter } from "@/graphs/models/utilities";

function isFunction<T>(value: MaybeGetter<T>): value is () => T {
	return typeof value === "function";
}

export function toValue<T>(value: MaybeGetter<T>): T {
	return isFunction(value) ? value() : value;
}
