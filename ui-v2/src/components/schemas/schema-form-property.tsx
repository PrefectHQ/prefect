import { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useId, useMemo } from "react";
import { SchemaFormInput } from "./schema-form-input";
import { SchemaFormPropertyDescription } from "./schema-form-property-description";
import { SchemaFormPropertyLabel } from "./schema-form-property-label";
import { useSchemaFormContext } from "./use-schema-form-context";
import { mergeSchemaPropertyDefinition } from "./utilities/mergeSchemaPropertyDefinition";

export type SchemaFormPropertyProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject | ReferenceObject;
	required: boolean;
	errors: unknown;
	showLabel?: boolean;
	showDescription?: boolean;
};

export function SchemaFormProperty({
	property: propertyDefinition,
	value,
	onValueChange,
	required,
	errors,
	showLabel = true,
	showDescription = true,
}: SchemaFormPropertyProps) {
	const { schema } = useSchemaFormContext();
	const id = useId();

	const property = useMemo(() => {
		return mergeSchemaPropertyDefinition(propertyDefinition, schema);
	}, [propertyDefinition, schema]);

	return (
		<div className="flex flex-col gap-2">
			{showLabel && (
				<SchemaFormPropertyLabel
					property={property}
					required={required}
					id={id}
				/>
			)}

			{showDescription && <SchemaFormPropertyDescription property={property} />}

			<SchemaFormInput
				property={property}
				value={value}
				onValueChange={onValueChange}
				errors={errors}
				id={id}
			/>
		</div>
	);
}
