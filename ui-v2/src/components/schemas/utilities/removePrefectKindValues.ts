import {
	isPrefectKindValue,
	isPrefectKindValueJson,
} from "../types/prefect-kind-value";
import type { SchemaFormValues } from "../types/values";
import { isArray, isRecord } from "./guards";

/**
 * Converts `__prefect_kind: "json"` wrapper values produced by the schema form
 * back into their native values. Work pool base job templates and block
 * documents are stored as plain JSON on the server, so they must not contain
 * the wrappers the form uses for editing free-form objects. Wrappers whose text
 * is empty or not valid JSON become `undefined` so malformed editor input is
 * never persisted as a string.
 */
export function removePrefectKindValues(
	values: SchemaFormValues,
): SchemaFormValues {
	return Object.fromEntries(
		Object.entries(values).map(([key, value]) => [
			key,
			removePrefectKindValue(value),
		]),
	);
}

export function removePrefectKindValue(value: unknown): unknown {
	if (isPrefectKindValueJson(value)) {
		if (value.value === undefined || value.value.trim() === "") {
			return undefined;
		}

		try {
			return removePrefectKindValue(JSON.parse(value.value));
		} catch {
			return undefined;
		}
	}

	if (isPrefectKindValue(value)) {
		return value;
	}

	if (isArray(value)) {
		return value.flatMap((item) => {
			const converted = removePrefectKindValue(item);
			return converted === undefined ? [] : [converted];
		});
	}

	if (isRecord(value)) {
		return removePrefectKindValues(value);
	}

	return value;
}
