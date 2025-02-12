import { SchemaObject } from "openapi-typescript";
import { PrimitivePropertyType, isPrimitivePropertyType } from "./primitives";

export type WithPosition = {
	position?: number;
};

export type PrefectObjectSubtype = {
	properties?: {
		[name: string]: WithPosition;
	};
};

export type BlockDocumentSubtype = {
	blockTypeSlug: string;
};

export type PrefectSchemaObject = BlockDocumentSubtype;

export type WithPrimitiveEnum = { enum: PrimitivePropertyType[] };

export function isWithPrimitiveEnum<T extends SchemaObject>(
	property: T,
): property is T & WithPrimitiveEnum {
	return (
		"enum" in property &&
		Array.isArray(property.enum) &&
		property.enum.every((value) => isPrimitivePropertyType(typeof value))
	);
}
