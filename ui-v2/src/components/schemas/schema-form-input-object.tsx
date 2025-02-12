import { ObjectSubtype, SchemaObject } from "openapi-typescript";
import { useMemo } from "react";
import { SchemaFormInput } from "./schema-form-input";
import { PrefectObjectSubtype } from "./types/schemas";
import { sortByPropertyPosition } from "./utilities/sortByPropertyPosition";

export type SchemaFormInputObjectProps = {
	values: Record<string, unknown> | undefined;
	onValuesChange: (values: Record<string, unknown>) => void;
	property: SchemaObject & ObjectSubtype & PrefectObjectSubtype;
	errors: unknown;
};

export function SchemaFormInputObject({
	values,
	onValuesChange,
	property,
	errors,
}: SchemaFormInputObjectProps) {
	function onPropertyValueChange(key: string, value: unknown) {
		onValuesChange({ ...values, [key]: value });
	}

	function getPropertyValue(key: string): unknown {
		return values?.[key];
	}

	function getPropertyErrors(key: string): unknown {
		return errors?.[key];
	}

	const properties = useMemo(() => {
		return Object.entries(property.properties ?? {}).sort(([, a], [, b]) =>
			sortByPropertyPosition(a, b),
		);
	}, [property.properties]);

	return properties.map(([key, property]) => {
		return (
			<SchemaFormInput
				key={key}
				value={getPropertyValue(key)}
				onValueChange={(value) => onPropertyValueChange(key, value)}
				property={property}
				errors={getPropertyErrors(key)}
			/>
		);
	});
}
