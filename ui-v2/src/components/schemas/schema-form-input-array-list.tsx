import { ArraySubtype, SchemaObject } from "openapi-typescript";
import { Button } from "../ui/button";
import { SchemaFormInputArrayItem } from "./schema-form-input-array-item";
import { SchemaFormPropertyErrors } from "./schema-form-property-errors";
import {
	SchemaFormErrors,
	SchemaValueIndexError,
	isSchemaValueIndexError,
} from "./types/errors";
import { isArray } from "./utilities/guards";

export type SchemaFormInputArrayListProps = {
	property: SchemaObject & ArraySubtype;
	values: unknown[] | undefined;
	onValuesChange: (values: unknown[] | undefined) => void;
	errors: SchemaFormErrors;
};

export function SchemaFormInputArrayList({
	property,
	values,
	onValuesChange,
	errors,
}: SchemaFormInputArrayListProps) {
	const isEmpty = values === undefined || values.length === 0;
	const canAddMore =
		property.maxItems === undefined ||
		(values?.length ?? 0) < (property.maxItems ?? Infinity);

	function getPropertyForIndex(index: number) {
		if (isArray(property.prefixItems) && index < property.prefixItems.length) {
			return property.prefixItems[index];
		}

		return property.items ?? { type: "string" };
	}

	function getErrorsForIndex(index: number) {
		return errors
			.filter(
				(error): error is SchemaValueIndexError =>
					isSchemaValueIndexError(error) && error.index === index,
			)
			.flatMap((error) => error.errors);
	}

	function handleValueChange(index: number, value: unknown) {
		const newValues = [...(values ?? [])];
		newValues[index] = value;
		onValuesChange(newValues);
	}

	function addItem() {
		const newValues = [...(values ?? []), undefined];

		onValuesChange(newValues);
	}

	function deleteItem(index: number) {
		const newValues = [...(values ?? [])];
		newValues.splice(index, 1);

		onValuesChange(newValues);
	}

	return (
		<>
			{isEmpty && (
				<p className="text-sm text-subdued italic">No items in this list</p>
			)}

			{values?.map((value, index) => (
				<div className="grid grid-cols-[1fr_auto] gap-2" key={index}>
					<div className="grid grid-cols-1 gap-2">
						<SchemaFormInputArrayItem
							key={index}
							items={getPropertyForIndex(index)}
							value={value}
							onValueChange={(value: unknown) =>
								handleValueChange(index, value)
							}
							errors={getErrorsForIndex(index)}
						/>
						<SchemaFormPropertyErrors errors={getErrorsForIndex(index)} />
					</div>
					<Button size="sm" variant="outline" onClick={() => deleteItem(index)}>
						Delete
					</Button>
				</div>
			))}

			{canAddMore && (
				<div className="flex justify-end">
					<Button size="sm" variant="outline" onClick={addItem}>
						Add item
					</Button>
				</div>
			)}

			{!canAddMore && (
				<p className="text-sm text-subdued text-right">
					You can&apos;t add more items
				</p>
			)}
		</>
	);
}
