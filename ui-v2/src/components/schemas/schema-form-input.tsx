import { SchemaFormInputArray } from "./schema-form-input-array";
import { SchemaFormInputBoolean } from "./schema-form-input-boolean";
import { SchemaFormInputInteger } from "./schema-form-input-integer";
import { SchemaFormInputNull } from "./schema-form-input-null";
import { SchemaFormInputNumber } from "./schema-form-input-number";
import { SchemaFormInputObject } from "./schema-form-input-object";
import { SchemaFormInputString } from "./schema-form-input-string";
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
		throw new Error("not implemented");
	}

	if ("blockTypeSlug" in property) {
		throw new Error("not implemented");
	}

	if ("anyOf" in property) {
		throw new Error("not implemented");
	}

	if ("allOf" in property) {
		throw new Error("not implemented");
	}

	if ("oneOf" in property) {
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

	// todo: handle types like ["string", "null"] which we can convert into a union type
	if (Array.isArray(property.type)) {
		throw new Error("not implemented");
	}

	if (property.type === undefined) {
		throw new Error("Schema type not implemented");
	}

	throw new Error(
		`Schema type not implemented: ${String(property.type satisfies never)}`,
	);
}
