import type { SchemaObject } from "openapi-typescript";
import { useMemo } from "react";

export type SchemaFormPropertyDescriptionProps = {
	property: SchemaObject;
};

export function SchemaFormPropertyDescription({
	property,
}: SchemaFormPropertyDescriptionProps) {
	// Description come from the doc strings which frequently have very short line lengths. We remove the single line breaks to make it easier to read.
	const description = useMemo(() => {
		return property.description?.replace(/\n(?!\n)/g, " ");
	}, [property.description]);

	// todo: support markdown
	return description && <p className="text-sm text-gray-500">{description}</p>;
}
