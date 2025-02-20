import { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useId, useMemo } from "react";
import { SchemaFormInput } from "./schema-form-input";
import { SchemaFormPropertyDescription } from "./schema-form-property-description";
import { SchemaFormPropertyErrors } from "./schema-form-property-errors";
import { SchemaFormPropertyLabel } from "./schema-form-property-label";
import { SchemaFormPropertyMenu } from "./schema-form-property-menu";
import {
	SchemaFormErrors,
	SchemaValueIndexError,
	SchemaValuePropertyError,
	isSchemaValueIndexError,
	isSchemaValuePropertyError,
} from "./types/errors";
import { useSchemaFormContext } from "./use-schema-form-context";
import { mergeSchemaPropertyDefinition } from "./utilities/mergeSchemaPropertyDefinition";

export type SchemaFormPropertyProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject | ReferenceObject;
	required: boolean;
	errors: SchemaFormErrors;
	showLabel?: boolean;
};

export function SchemaFormProperty({
	property: propertyDefinition,
	value,
	onValueChange,
	required,
	errors,
	showLabel = true,
}: SchemaFormPropertyProps) {
	const { schema } = useSchemaFormContext();
	const id = useId();

	const property = useMemo(() => {
		return mergeSchemaPropertyDefinition(propertyDefinition, schema);
	}, [propertyDefinition, schema]);

	const nestedErrors = useMemo(() => {
		return errors.filter(
			(error): error is SchemaValuePropertyError | SchemaValueIndexError =>
				isSchemaValuePropertyError(error) || isSchemaValueIndexError(error),
		);
	}, [errors]);

	return (
		<div className="flex flex-col gap-2">
			{showLabel && (
				<div className="grid grid-cols-[1fr_auto] items-center gap-2">
					<SchemaFormPropertyLabel
						property={property}
						required={required}
						id={id}
					/>
					<div className="ml-auto">
						<SchemaFormPropertyMenu
							value={value}
							onValueChange={onValueChange}
							property={property}
						/>
					</div>
				</div>
			)}

			<SchemaFormPropertyDescription property={property} />

			<SchemaFormInput
				property={property}
				value={value}
				onValueChange={onValueChange}
				errors={nestedErrors}
				id={id}
			/>

			<SchemaFormPropertyErrors errors={errors} />
		</div>
	);
}
