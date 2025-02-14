import { SchemaFormInputArray } from "./schema-form-input-array";
import { SchemaFormInputBoolean } from "./schema-form-input-boolean";
import { SchemaFormInputInteger } from "./schema-form-input-integer";
import { SchemaFormInputNull } from "./schema-form-input-null";
import { SchemaFormInputNumber } from "./schema-form-input-number";
import { SchemaFormInputObject } from "./schema-form-input-object";
import { SchemaFormInputPrefectKindJson } from "./schema-form-input-prefect-kind-json";
import { SchemaFormInputPrefectKindNone } from "./schema-form-input-prefect-kind-none";
import { SchemaFormInputString } from "./schema-form-input-string";
import { SchemaFormInputUnknown } from "./schema-form-input-unknown";
import { isPrefectKindValue } from "./types/prefect-kind-value";
import { PrefectSchemaObject } from "./types/schemas";
import { asArray, asObject, asType } from "./utilities/asType";

export type SchemaFormInputProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	errors: unknown;
	property: PrefectSchemaObject;
};

export function SchemaFormInput({
	value,
	onValueChange,
	property,
	errors,
}: SchemaFormInputProps) {
	if (isPrefectKindValue(value)) {
		if (isPrefectKindValue(value, "json")) {
			return (
				<SchemaFormInputPrefectKindJson
					value={value}
					onValueChange={onValueChange}
					errors={errors}
				/>
			);
		}

		if (isPrefectKindValue(value, "jinja")) {
			throw new Error("not implemented");
		}

		if (isPrefectKindValue(value, "none")) {
			return (
				<SchemaFormInputPrefectKindNone
					value={value}
					onValueChange={onValueChange}
					errors={errors}
					property={property}
				/>
			);
		}

		// @ts-expect-error This is an exhaustive check. If a prefect kind is not implemented this will get flaggged.
		throw new Error(`Prefect kind not implemented: ${value.__prefect_kind}`);
	}

	if ("blockTypeSlug" in property) {
		throw new Error("not implemented");
	}

	if ("anyOf" in property || "oneOf" in property) {
		throw new Error("not implemented");
	}

	// this is the same as an anyOf so we can convert it here and use the same logic component
	if (Array.isArray(property.type)) {
		throw new Error("not implemented");
	}

	if ("allOf" in property) {
		throw new Error("not implemented");
	}

	if (property.type === "string") {
		return (
			<SchemaFormInputString
				value={asType(value, String)}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
			/>
		);
	}

	if (property.type === "integer") {
		return (
			<SchemaFormInputInteger
				value={asType(value, Number)}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
			/>
		);
	}

	if (property.type === "number") {
		return (
			<SchemaFormInputNumber
				value={asType(value, Number)}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
			/>
		);
	}

	if (property.type === "boolean") {
		return (
			<SchemaFormInputBoolean
				value={asType(value, Boolean)}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
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
			/>
		);
	}

	if (property.type === "null") {
		return (
			<SchemaFormInputNull
				value={null}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
			/>
		);
	}

	if (property.type === undefined) {
		return (
			<SchemaFormInputUnknown
				value={value}
				onValueChange={onValueChange}
				property={property}
				errors={errors}
			/>
		);
	}

	throw new Error(
		`Schema type not implemented: ${String(property.type satisfies never)}`,
	);
}
