import { CheckedState } from "@radix-ui/react-checkbox";
import { BooleanSubtype, SchemaObject } from "openapi-typescript";
import { Checkbox } from "../ui/checkbox";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { asType } from "./utilities/asType";

type SchemaFormInputBooleanProps = {
	value: boolean | undefined;
	onValueChange: (value: boolean | undefined) => void;
	property: SchemaObject & BooleanSubtype;
	errors: unknown;
	id: string;
};

export function SchemaFormInputBoolean({
	value,
	onValueChange,
	property,
	errors,
	id,
}: SchemaFormInputBooleanProps) {
	function onCheckedChange(checked: CheckedState) {
		onValueChange(asType(checked, Boolean));
	}

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

	return <Checkbox checked={value} onCheckedChange={onCheckedChange} id={id} />;
}
