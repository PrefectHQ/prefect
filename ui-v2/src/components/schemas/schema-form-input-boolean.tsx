import type { CheckedState } from "@radix-ui/react-checkbox";
import type { BooleanSubtype, SchemaObject } from "openapi-typescript";
import { Switch } from "@/components/ui/switch";
import { SchemaFormInputEnum } from "./schema-form-input-enum";
import { isWithPrimitiveEnum } from "./types/schemas";
import { asType } from "./utilities/asType";

type SchemaFormInputBooleanProps = {
	value: boolean | undefined;
	onValueChange: (value: boolean | undefined) => void;
	property: SchemaObject & BooleanSubtype;
	id: string;
};

export function SchemaFormInputBoolean({
	value,
	onValueChange,
	property,
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
				id={id}
			/>
		);
	}

	return <Switch checked={value} onCheckedChange={onCheckedChange} id={id} />;
}
