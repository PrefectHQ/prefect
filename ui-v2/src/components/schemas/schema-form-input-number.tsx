import { NumberSubtype, SchemaObject } from "openapi-typescript";
import { Input } from "../ui/input";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";

type SchemaFormInputNumberProps = {
	value: number | undefined;
	onValueChange: (value: number | undefined) => void;
	property: SchemaObject & NumberSubtype;
	errors: unknown;
};

export function SchemaFormInputNumber({
	value,
	onValueChange,
	property,
	errors,
}: SchemaFormInputNumberProps) {
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

	function handleChange(value: string) {
		if (value === "") {
			onValueChange(undefined);
		} else {
			onValueChange(Number(value));
		}
	}

	return (
		<Input
			type="number"
			min={property.minimum}
			max={property.maximum}
			value={value ?? ""}
			onChange={(e) => handleChange(e.target.value)}
		/>
	);
}
