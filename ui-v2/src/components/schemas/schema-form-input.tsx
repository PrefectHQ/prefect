import type { SchemaObject } from "openapi-typescript";
import { SchemaFormInputAllOf } from "./schema-form-input-all-of";
import { SchemaFormInputAnyOf } from "./schema-form-input-any-of";
import { SchemaFormInputArray } from "./schema-form-input-array";
import { SchemaFormInputBoolean } from "./schema-form-input-boolean";
import { SchemaFormInputInteger } from "./schema-form-input-integer";
import { SchemaFormInputNull } from "./schema-form-input-null";
import { SchemaFormInputNumber } from "./schema-form-input-number";
import { SchemaFormInputObject } from "./schema-form-input-object";
import { SchemaFormInputPrefectKindJson } from "./schema-form-input-prefect-kind-json";
import { SchemaFormInputString } from "./schema-form-input-string";
import { SchemaFormInputUnknown } from "./schema-form-input-unknown";
import type { SchemaFormErrors } from "./types/errors";
import { isPrefectKindValue } from "./types/prefect-kind-value";
import { asArray, asObject, asType } from "./utilities/asType";
import {
	isAllOfObject,
	isAnyOfObject,
	isOneOfObject,
} from "./utilities/guards";

export type SchemaFormInputProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	errors: SchemaFormErrors;
	property: SchemaObject;
	id: string;
	nested?: boolean;
};

export function SchemaFormInput({
	value,
	onValueChange,
	errors,
	property,
	id,
	nested = true,
}: SchemaFormInputProps) {
	if (isPrefectKindValue(value)) {
		if (isPrefectKindValue(value, "json")) {
			return (
				<SchemaFormInputPrefectKindJson
					value={value}
					onValueChange={onValueChange}
					id={id}
				/>
			);
		}

		if (isPrefectKindValue(value, "jinja")) {
			throw new Error("not implemented");
		}

		// @ts-expect-error This is an exhaustive check. If a prefect kind is not implemented this will get flaggged.
		throw new Error(`Prefect kind not implemented: ${value.__prefect_kind}`);
	}

	if ("blockTypeSlug" in property) {
		throw new Error("not implemented");
	}

	if (isAnyOfObject(property)) {
		return (
			<SchemaFormInputAnyOf
				value={value}
				property={property}
				onValueChange={onValueChange}
				errors={errors}
			/>
		);
	}

	// According to the spec, anyOf and oneOf are different. But pydantic always uses anyOf even when it should use oneOf. So we treat them the same.
	// This block shouldn't ever be hit because we handle anyOf above. But this offers some typesafety and a fallback in case of future changes.
	// https://swagger.io/docs/specification/v3_0/data-models/oneof-anyof-allof-not/
	// https://github.com/pydantic/pydantic/issues/4125
	if (isOneOfObject(property)) {
		const propertyWithAnyOf = {
			...property,
			anyOf: property.oneOf,
		};

		return (
			<SchemaFormInputAnyOf
				value={value}
				property={propertyWithAnyOf}
				onValueChange={onValueChange}
				errors={errors}
			/>
		);
	}

	// this is the same as an anyOf so we can convert it here and use the same logic component
	if (Array.isArray(property.type)) {
		const propertyWithAnyOf = {
			...property,
			anyOf: Object.values(property.type).map((type) => ({
				type,
			})),
		};

		return (
			<SchemaFormInputAnyOf
				value={value}
				property={propertyWithAnyOf}
				onValueChange={onValueChange}
				errors={errors}
			/>
		);
	}

	if (isAllOfObject(property)) {
		return (
			<SchemaFormInputAllOf
				value={value}
				onValueChange={onValueChange}
				errors={errors}
				property={property}
				id={id}
			/>
		);
	}

	if (property.type === "string") {
		return (
			<SchemaFormInputString
				value={asType(value, String)}
				onValueChange={onValueChange}
				property={property}
				id={id}
			/>
		);
	}

	if (property.type === "integer") {
		return (
			<SchemaFormInputInteger
				value={asType(value, Number)}
				onValueChange={onValueChange}
				property={property}
				id={id}
			/>
		);
	}

	if (property.type === "number") {
		return (
			<SchemaFormInputNumber
				value={asType(value, Number)}
				onValueChange={onValueChange}
				property={property}
				id={id}
			/>
		);
	}

	if (property.type === "boolean") {
		return (
			<SchemaFormInputBoolean
				value={asType(value, Boolean)}
				onValueChange={onValueChange}
				property={property}
				id={id}
			/>
		);
	}

	if (property.type === "object") {
		return (
			<SchemaFormInputObject
				values={asObject(value)}
				property={property}
				onValuesChange={onValueChange}
				errors={errors}
				nested={nested}
			/>
		);
	}

	if (property.type === "array") {
		return (
			<SchemaFormInputArray
				values={asArray(value)}
				property={property}
				onValuesChange={onValueChange}
				errors={errors}
				id={id}
			/>
		);
	}

	if (property.type === "null") {
		return <SchemaFormInputNull />;
	}

	if (property.type === undefined) {
		return (
			<SchemaFormInputUnknown
				value={value}
				onValueChange={onValueChange}
				property={property}
				id={id}
			/>
		);
	}

	throw new Error(
		`Schema type not implemented: ${String(property.type satisfies never)}`,
	);
}
