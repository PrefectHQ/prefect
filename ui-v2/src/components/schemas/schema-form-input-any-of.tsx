import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useRef, useState } from "react";
import { Card } from "../ui/card";
import { ToggleGroup, ToggleGroupItem } from "../ui/toggle-group";
import { SchemaFormProperty } from "./schema-form-property";
import type { SchemaFormErrors } from "./types/errors";
import { useSchemaFormContext } from "./use-schema-form-context";
import { getIndexForAnyOfPropertyValue } from "./utilities/getIndexForAnyOfPropertyValue";
import { getSchemaObjectLabel } from "./utilities/getSchemaObjectLabel";
export type SchemaFormInputAnyOfProps = {
	value: unknown;
	property: SchemaObject & { anyOf: (SchemaObject | ReferenceObject)[] };
	onValueChange: (value: unknown) => void;
	errors: SchemaFormErrors;
};

export function SchemaFormInputAnyOf({
	value,
	property,
	onValueChange,
	errors,
}: SchemaFormInputAnyOfProps) {
	const { schema } = useSchemaFormContext();
	const [selectedIndex, setSelectedIndex] = useState(
		getIndexForAnyOfPropertyValue({ value, property, schema }),
	);
	const values = useRef(new Map<number, unknown>());

	function onSelectedIndexChange(newSelectedIndexValue: string) {
		const newSelectedIndex = Number.parseInt(newSelectedIndexValue);

		if (Number.isNaN(newSelectedIndex)) {
			throw new Error(`Invalid index: ${newSelectedIndexValue}`);
		}

		values.current.set(selectedIndex, value);

		setSelectedIndex(newSelectedIndex);

		onValueChange(values.current.get(newSelectedIndex));
	}

	return (
		<div className="grid grid-cols-1 gap-2">
			<ToggleGroup
				size="sm"
				variant="outline"
				type="single"
				value={selectedIndex.toString()}
				onValueChange={onSelectedIndexChange}
				className="justify-start"
			>
				{property.anyOf.map((option, index) => {
					const label = getSchemaObjectLabel(option, schema);
					return (
						<ToggleGroupItem key={label} value={index.toString()}>
							{label}
						</ToggleGroupItem>
					);
				})}
			</ToggleGroup>

			<Card className="p-2">
				<SchemaFormProperty
					value={value}
					property={property.anyOf[selectedIndex]}
					onValueChange={onValueChange}
					errors={errors}
					showLabel={false}
					nested={false}
					// This form property is nested within the anyOf property, so hard coding required to false because the anyOf property itself is what can be required
					required={false}
				/>
			</Card>
		</div>
	);
}
