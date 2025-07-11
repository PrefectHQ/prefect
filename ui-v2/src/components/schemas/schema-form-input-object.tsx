import type { ObjectSubtype, SchemaObject } from "openapi-typescript";
import { useCallback, useMemo, useRef } from "react";
import useDebounceCallback from "@/hooks/use-debounce-callback";
import { Card } from "../ui/card";
import { SchemaFormProperty } from "./schema-form-property";
import {
	isSchemaValuePropertyError,
	type SchemaFormErrors,
} from "./types/errors";
import type { PrefectObjectSubtype } from "./types/schemas";
import { sortByPropertyPosition } from "./utilities/sortByPropertyPosition";

export type SchemaFormInputObjectProps = {
	values: Record<string, unknown> | undefined;
	onValuesChange: (values: Record<string, unknown> | undefined) => void;
	property: SchemaObject & ObjectSubtype & PrefectObjectSubtype;
	errors: SchemaFormErrors;
	nested: boolean;
};

export function SchemaFormInputObject({
	values,
	onValuesChange,
	property,
	errors,
	nested,
}: SchemaFormInputObjectProps) {
	const patches = useRef<{ key: string; value: unknown }[]>([]);

	const flush = useDebounceCallback(
		useCallback(() => {
			const newValues = { ...values };

			for (const { key, value } of patches.current) {
				newValues[key] = value;

				if (value === undefined) {
					delete newValues[key];
				}
			}

			patches.current = [];

			if (Object.keys(newValues).length === 0) {
				onValuesChange(undefined);
				return;
			}

			onValuesChange(newValues);
		}, [values, onValuesChange]),
		10,
	);

	function onPropertyValueChange(key: string, value: unknown) {
		patches.current.push({ key, value });

		flush();
	}

	function getPropertyValue(key: string): unknown {
		return values?.[key];
	}

	function getPropertyErrors(key: string): SchemaFormErrors {
		return errors
			.filter(isSchemaValuePropertyError)
			.filter((error) => error.property === key)
			.flatMap((error) => error.errors);
	}

	const properties = useMemo(() => {
		return Object.entries(property.properties ?? {}).sort(([, a], [, b]) =>
			sortByPropertyPosition(a, b),
		);
	}, [property.properties]);

	const output = (
		<div className="flex flex-col gap-4">
			{properties.map(([key, subProperty]) => (
				<SchemaFormProperty
					key={key}
					value={getPropertyValue(key)}
					onValueChange={(value) => onPropertyValueChange(key, value)}
					property={subProperty}
					errors={getPropertyErrors(key)}
					required={Boolean(property.required?.includes(key))}
				/>
			))}
		</div>
	);

	if (nested) {
		return <Card className="p-2">{output}</Card>;
	}

	return output;
}
