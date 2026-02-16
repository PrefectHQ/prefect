import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useRef, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
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
		const newSelectedIndex = Number.parseInt(newSelectedIndexValue, 10);

		if (Number.isNaN(newSelectedIndex)) {
			throw new Error(`Invalid index: ${newSelectedIndexValue}`);
		}

		values.current.set(selectedIndex, value);

		setSelectedIndex(newSelectedIndex);

		onValueChange(values.current.get(newSelectedIndex));
	}

	return (
		<Tabs
			value={selectedIndex.toString()}
			onValueChange={onSelectedIndexChange}
		>
			<TabsList>
				{property.anyOf.map((option, index) => {
					const label = getSchemaObjectLabel(option, schema);
					return (
						<TabsTrigger key={label} value={index.toString()}>
							{label}
						</TabsTrigger>
					);
				})}
			</TabsList>

			<TabsContent value={selectedIndex.toString()}>
				<SchemaFormProperty
					key={selectedIndex}
					value={value}
					property={property.anyOf[selectedIndex]}
					onValueChange={onValueChange}
					errors={errors}
					showLabel={false}
					nested={false}
					required={false}
				/>
			</TabsContent>
		</Tabs>
	);
}
