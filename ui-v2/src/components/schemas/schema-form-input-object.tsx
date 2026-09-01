import type { ObjectSubtype, SchemaObject } from "openapi-typescript";
import { useCallback, useEffect, useMemo, useRef } from "react";
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

function hasDefinedProperties(property: SchemaObject & ObjectSubtype): boolean {
	return (
		property.properties !== undefined &&
		Object.keys(property.properties).length > 0
	);
}

export function SchemaFormInputObject({
	values,
	onValuesChange,
	property,
	errors,
	nested,
}: SchemaFormInputObjectProps) {
	const isOpenObject = !hasDefinedProperties(property);
	// Child inputs can emit in the same turn and parents can echo stale values.
	// Retain patches until acknowledged, but flush before the next browser event.
	const pendingPatches = useRef(new Map<string, unknown>());
	const flushScheduled = useRef(false);
	const currentProps = useRef({ values, onValuesChange });
	currentProps.current = { values, onValuesChange };

	useEffect(() => {
		if (isOpenObject && nested && !values) {
			onValuesChange({
				__prefect_kind: "json",
			});
		}
	}, [isOpenObject, nested, values, onValuesChange]);

	const flushPatches = useCallback(() => {
		flushScheduled.current = false;
		const { values: currentValues, onValuesChange: emitValues } =
			currentProps.current;
		const newValues = { ...currentValues };

		for (const [key, value] of pendingPatches.current) {
			newValues[key] = value;

			if (value === undefined) {
				delete newValues[key];
			}
		}

		emitValues(Object.keys(newValues).length === 0 ? undefined : newValues);
	}, []);

	const scheduleFlush = useCallback(() => {
		if (flushScheduled.current) {
			return;
		}

		flushScheduled.current = true;
		queueMicrotask(flushPatches);
	}, [flushPatches]);

	useEffect(() => {
		for (const [key, value] of pendingPatches.current) {
			const acknowledged =
				value === undefined
					? !Object.hasOwn(values ?? {}, key)
					: Object.is(values?.[key], value);

			if (acknowledged) {
				pendingPatches.current.delete(key);
			}
		}

		if (pendingPatches.current.size > 0) {
			scheduleFlush();
		}
	}, [values, scheduleFlush]);

	const properties = useMemo(() => {
		return Object.entries(property.properties ?? {}).sort(([, a], [, b]) =>
			sortByPropertyPosition(a, b),
		);
	}, [property.properties]);

	if (isOpenObject && nested) {
		return null;
	}

	function onPropertyValueChange(key: string, value: unknown) {
		pendingPatches.current.set(key, value);

		scheduleFlush();
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
