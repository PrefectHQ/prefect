import {
	IntegerSubtype,
	NumberSubtype,
	SchemaObject,
} from "openapi-typescript";
import { Input } from "../ui/input";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";

type SchemaFormInputIntegerProps = {
	value: number | undefined;
	onValueChange: (value: number | undefined) => void;
	property: SchemaObject & (NumberSubtype | IntegerSubtype);
	errors: unknown;
	id: string;
};

export function SchemaFormInputInteger({
	value,
	onValueChange,
	property,
	errors,
	id,
}: SchemaFormInputIntegerProps) {
	if (isWithPrimitiveEnum(property)) {
		return (
			<SchemaFormInputEnum
				multiple={false}
				value={value}
				property={property}
				onValueChange={onValueChange}
				errors={errors}
				id={id}
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
			step="1"
			onChange={(e) => handleChange(e.target.value)}
			id={id}
		/>
	);
}
