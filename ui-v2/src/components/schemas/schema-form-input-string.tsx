import { SchemaObject, StringSubtype } from "openapi-typescript";
import { Input } from "../ui/input";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";

export type SchemaFormInputStringProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	property: SchemaObject & StringSubtype;
	errors: unknown;
};

export function SchemaFormInputString({
	value,
	onValueChange,
	errors,
	property,
}: SchemaFormInputStringProps) {
	if (isWithPrimitiveEnum(property)) {
		return (
			<SchemaFormInputEnum
				multiple={false}
				value={value}
				property={property}
				onValueChange={onValueChange}
				errors={errors}
			/>
		);
	}

	if (property.format) {
		throw new Error("not implemented");
	}

	return (
		<Input
			type="text"
			value={value ?? ""}
			onChange={(e) => onValueChange(e.target.value)}
		/>
	);
}
