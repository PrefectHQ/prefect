import type { SchemaObject } from "openapi-typescript";
import { useEffect } from "react";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { asPrimitive } from "./utilities/asType";

export type SchemaFormInputUnknownProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject & { type: undefined };
	id: string;
};

export function SchemaFormInputUnknown({
	value,
	onValueChange,
	property,
	id,
}: SchemaFormInputUnknownProps) {
	// if this isn't a simple enum we want to autoamtically switch to json
	useEffect(() => {
		if (!isWithPrimitiveEnum(property)) {
			onValueChange({
				__prefect_kind: "json",
			});
		}
	}, [property, onValueChange]);

	if (isWithPrimitiveEnum(property)) {
		return (
			<SchemaFormInputEnum
				multiple={false}
				value={asPrimitive(value)}
				property={property}
				onValueChange={onValueChange}
				id={id}
			/>
		);
	}

	return null;
}
