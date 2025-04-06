import type { SchemaObject } from "openapi-typescript";
import { useMemo } from "react";
import { Label } from "../ui/label";
import { useSchemaFormContext } from "./use-schema-form-context";
import { getSchemaObjectLabel } from "./utilities/getSchemaObjectLabel";

export type SchemaFormPropertyLabelProps = {
	property: SchemaObject;
	required: boolean;
	id: string;
};

export function SchemaFormPropertyLabel({
	property,
	required,
	id,
}: SchemaFormPropertyLabelProps) {
	const { schema } = useSchemaFormContext();

	const label = useMemo(() => {
		const label = getSchemaObjectLabel(property, schema);

		if (required) {
			return label;
		}

		return `${label} (Optional)`;
	}, [property, required, schema]);

	return <Label htmlFor={id}>{label}</Label>;
}
