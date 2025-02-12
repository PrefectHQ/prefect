import { Label } from "@/components/ui/label";
import { SchemaObject } from "openapi-typescript";
import { useMemo } from "react";
import { SchemaFormInput } from "./schema-form-input";

export type SchemaFormPropertyProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject;
	required: boolean;
	errors: unknown;
};

export function SchemaFormProperty({
	property,
	value,
	onValueChange,
	required,
	errors,
}: SchemaFormPropertyProps) {
	const label = useMemo(() => {
		const label = property.title ?? "Field";

		if (required) {
			return label;
		}

		return `${label} (Optional)`;
	}, [property.title, required]);

	const description = useMemo(() => {
		return property.description?.replace(/\n(?!\n)/g, " ");
	}, [property.description]);

	return (
		<div className="flex flex-col gap-2">
			<Label htmlFor={property.title}>{label}</Label>

			{/* todo: add markdown support */}
			{description && <p className="text-sm text-gray-500">{description}</p>}

			<SchemaFormInput
				property={property}
				value={value}
				onValueChange={onValueChange}
				errors={errors}
			/>
		</div>
	);
}
