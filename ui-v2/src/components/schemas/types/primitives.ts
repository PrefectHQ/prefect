import { createTuple } from "@/utils/utils";

export const {
	values: primitivePropertyTypes,
	isValue: isPrimitivePropertyType,
} = createTuple(["string", "integer", "number", "boolean"]);

export type PrimitivePropertyType = (typeof primitivePropertyTypes)[number];

export type PrimitiveProperty = number | string | boolean;
