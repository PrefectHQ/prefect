import { SchemaObject, StringSubtype } from "openapi-typescript";
import { Input } from "../ui/input";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { SchemaFormInputStringFormatDate } from "./schema-form-input-string-format-date";

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

	if (property.format === "date") {
		return <SchemaFormInputStringFormatDate value={value} onValueChange={onValueChange} errors={errors} />
	}
	
	if (property.format === "date-time") {
		throw new Error("date-time format not implemented");
	}

	return (
		<Input
			type="text"
			value={value ?? ""}
			onChange={(e) => onValueChange(e.target.value)}
		/>
	);
}
