import type { SchemaObject, StringSubtype } from "openapi-typescript";
import { Textarea } from "../ui/textarea";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { SchemaFormInputStringFormatDate } from "./schema-form-input-string-format-date";
import { SchemaFormInputStringFormatDateTime } from "./schema-form-input-string-format-datetime";
import { SchemaFormInputStringFormatJson } from "./schema-form-input-string-format-json";
import { isWithPrimitiveEnum } from "./types/schemas";

export type SchemaFormInputStringProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	property: SchemaObject & StringSubtype;
	id: string;
};

export function SchemaFormInputString({
	value,
	onValueChange,
	property,
	id,
}: SchemaFormInputStringProps) {
	function handleChange(value: string | undefined) {
		onValueChange(value || undefined);
	}

	if (isWithPrimitiveEnum(property)) {
		return (
			<SchemaFormInputEnum
				multiple={false}
				value={value}
				property={property}
				onValueChange={handleChange}
				id={id}
			/>
		);
	}

	if (property.format === "date") {
		return (
			<SchemaFormInputStringFormatDate
				value={value}
				onValueChange={handleChange}
				id={id}
			/>
		);
	}

	if (property.format === "date-time") {
		return (
			<SchemaFormInputStringFormatDateTime
				value={value}
				onValueChange={handleChange}
				id={id}
			/>
		);
	}

	if (property.format === "json-string") {
		return (
			<SchemaFormInputStringFormatJson
				value={value}
				onValueChange={handleChange}
				id={id}
			/>
		);
	}

	return (
		<Textarea
			value={value ?? ""}
			rows={1}
			className="min-h-min"
			onChange={(e) => handleChange(e.target.value)}
			id={id}
		/>
	);
}
