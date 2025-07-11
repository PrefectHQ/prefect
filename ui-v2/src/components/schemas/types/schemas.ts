import type { ObjectSubtype, SchemaObject } from "openapi-typescript";
import {
	isPrimitivePropertyType,
	type PrimitivePropertyType,
} from "./primitives";

export type WithPosition = {
	position?: number;
};

export type PrefectObjectSubtype = {
	properties?: {
		[name: string]: WithPosition;
	};
};

export type WithBlockDocumentSlug = {
	blockTypeSlug?: string;
};

export type WithDefinitions = {
	definitions?: {
		[name: string]: SchemaObject;
	};
};

export type PrefectSchemaObject = SchemaObject &
	ObjectSubtype &
	WithBlockDocumentSlug &
	WithDefinitions;

export type WithPrimitiveEnum = {
	enum: PrimitivePropertyType[];
};

export function isWithPrimitiveEnum<T extends SchemaObject>(
	property: T,
): property is T & WithPrimitiveEnum {
	return (
		"enum" in property &&
		Array.isArray(property.enum) &&
		property.enum.every((value) => isPrimitivePropertyType(typeof value))
	);
}
