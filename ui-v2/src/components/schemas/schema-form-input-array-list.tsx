import { ArraySubtype, SchemaObject } from "openapi-typescript";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { SchemaFormInputArrayItem } from "./schema-form-input-array-item";
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

	function getFirstForIndex(index: number): boolean {
		return index === 0;
	}

	function getLastForIndex(index: number): boolean {
		return index === (values?.length ?? 0) - 1;
	}

	function getCanMoveForIndex(index: number): boolean {
		const isPrefixItem =
			isArray(property.prefixItems) && index < property.prefixItems.length;

		return !isPrefixItem;
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

	function moveItem(from: number, to: number) {
		const newValues = [...(values ?? [])];
		newValues.splice(to, 0, newValues.splice(from, 1)[0]);
		onValuesChange(newValues);
	}

	function deleteItem(index: number) {
		const newValues = [...(values ?? [])];
		newValues.splice(index, 1);

		onValuesChange(newValues);
	}

	return (
		<Card className="flex flex-col gap-2 p-2">
			{isEmpty && (
				<p className="text-sm text-subdued italic">No items in this list</p>
			)}

			{values?.map((value, index) => (
				<SchemaFormInputArrayItem
					key={index}
					items={getPropertyForIndex(index)}
					value={value}
					onValueChange={(value) => handleValueChange(index, value)}
					errors={getErrorsForIndex(index)}
					onDelete={() => deleteItem(index)}
					first={getFirstForIndex(index)}
					last={getLastForIndex(index)}
					canMove={getCanMoveForIndex(index)}
					moveUp={() => moveItem(index, index - 1)}
					moveDown={() => moveItem(index, index + 1)}
				/>
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
		</Card>
	);
}
