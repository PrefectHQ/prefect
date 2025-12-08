import type { components } from "@/api/prefect";
import { isRecord } from "../utilities/guards";

export type SchemaValueError = string;
export type SchemaValuePropertyError =
	components["schemas"]["SchemaValuePropertyError"];
export type SchemaValueIndexError =
	components["schemas"]["SchemaValueIndexError"];

export type SchemaFormNestedError =
	// eslint-disable-next-line @typescript-eslint/no-redundant-type-constituents
	| SchemaValuePropertyError
	// eslint-disable-next-line @typescript-eslint/no-redundant-type-constituents
	| SchemaValueIndexError;
export type SchemaFormError =
	| SchemaValueError
	// eslint-disable-next-line @typescript-eslint/no-redundant-type-constituents
	| SchemaFormNestedError;
export type SchemaFormErrors = SchemaFormError[];

export function isSchemaValueError(error: unknown): error is SchemaValueError {
	return typeof error === "string";
}

export function isSchemaValuePropertyError(
	error: unknown,
): error is SchemaValuePropertyError {
	return isRecord(error) && "property" in error;
}

export function isSchemaValueIndexError(
	error: unknown,
): error is SchemaValueIndexError {
	return isRecord(error) && "index" in error;
}
