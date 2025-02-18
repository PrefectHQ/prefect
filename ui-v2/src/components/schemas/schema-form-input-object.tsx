import { ObjectSubtype, SchemaObject } from "openapi-typescript";
import { useMemo } from "react";
import { SchemaFormProperty } from "./schema-form-property";
import { PrefectObjectSubtype } from "./types/schemas";
import { sortByPropertyPosition } from "./utilities/sortByPropertyPosition";

export type SchemaFormInputObjectProps = {
	values: Record<string, unknown> | undefined;
	onValuesChange: (values: Record<string, unknown> | undefined) => void;
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
		const newValues = { ...values, [key]: value };

		if (value === undefined) {
			delete newValues[key];
		}

		if (Object.keys(newValues).length === 0) {
			onValuesChange(undefined);
			return;
		}

		onValuesChange(newValues);
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

	return properties.map(([key, subProperty]) => {
		return (
			<SchemaFormProperty
				key={key}
				value={getPropertyValue(key)}
				onValueChange={(value) => onPropertyValueChange(key, value)}
				property={subProperty}
				errors={getPropertyErrors(key)}
				required={Boolean(property.required?.includes(key))}
			/>
		);
	});
}
