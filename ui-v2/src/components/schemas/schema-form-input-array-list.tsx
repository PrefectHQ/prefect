import {
	closestCenter,
	DndContext,
	type DragEndEvent,
	KeyboardSensor,
	PointerSensor,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import {
	SortableContext,
	sortableKeyboardCoordinates,
	verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { ArraySubtype, SchemaObject } from "openapi-typescript";
import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { SchemaFormInputArrayItem } from "./schema-form-input-array-item";
import {
	isSchemaValueIndexError,
	type SchemaFormErrors,
	type SchemaValueIndexError,
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
		(values?.length ?? 0) < (property.maxItems ?? Number.POSITIVE_INFINITY);

	const prefixItemsCount = isArray(property.prefixItems)
		? property.prefixItems.length
		: 0;

	const sensors = useSensors(
		useSensor(PointerSensor),
		useSensor(KeyboardSensor, {
			coordinateGetter: sortableKeyboardCoordinates,
		}),
	);

	const [localKeyedValues, setLocalKeyedValues] = useState<
		{
			key: string;
			value: unknown;
		}[]
	>(
		values?.map((value) => ({
			key: uuidv4(),
			value,
		})) ?? [],
	);

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

	function handleValueChange(key: string, value: unknown) {
		setLocalKeyedValues(
			localKeyedValues.map((item) =>
				item.key === key ? { ...item, value } : item,
			),
		);
	}

	function addItem() {
		const newKeyedValues = [
			...localKeyedValues,
			{ key: uuidv4(), value: undefined },
		];
		setLocalKeyedValues(newKeyedValues);
		onValuesChange(newKeyedValues.map(({ value }) => value));
	}

	function moveItem(from: number, to: number) {
		const newValues = [...localKeyedValues];
		newValues.splice(to, 0, newValues.splice(from, 1)[0]);
		setLocalKeyedValues(newValues);
		onValuesChange(newValues.map(({ value }) => value));
	}

	function moveToTop(index: number) {
		moveItem(index, 0);
	}

	function moveToBottom(index: number) {
		moveItem(index, localKeyedValues.length - 1);
	}

	function deleteItem(key: string) {
		const newValues = localKeyedValues.filter((item) => item.key !== key);
		setLocalKeyedValues(newValues);
		onValuesChange(newValues.map(({ value }) => value));
	}

	function handleDragEnd(event: DragEndEvent) {
		const { active, over } = event;

		if (over && active.id !== over.id) {
			const oldIndex = localKeyedValues.findIndex(
				(item) => item.key === active.id,
			);
			const newIndex = localKeyedValues.findIndex(
				(item) => item.key === over.id,
			);

			if (oldIndex !== -1 && newIndex !== -1) {
				moveItem(oldIndex, newIndex);
			}
		}
	}

	// Get the keys of items that can be dragged (non-prefix items)
	const sortableKeys = localKeyedValues
		.slice(prefixItemsCount)
		.map((item) => item.key);

	return (
		<Card className="flex flex-col gap-2 p-2">
			{isEmpty && (
				<p className="text-sm text-subdued italic">No items in this list</p>
			)}

			<DndContext
				sensors={sensors}
				collisionDetection={closestCenter}
				onDragEnd={handleDragEnd}
			>
				<SortableContext
					items={sortableKeys}
					strategy={verticalListSortingStrategy}
				>
					{localKeyedValues?.map(({ key, value }, index) => (
						<SchemaFormInputArrayItem
							key={key}
							itemKey={key}
							items={getPropertyForIndex(index)}
							value={value}
							onValueChange={(value) => handleValueChange(key, value)}
							errors={getErrorsForIndex(index)}
							onDelete={() => deleteItem(key)}
							first={getFirstForIndex(index)}
							last={getLastForIndex(index)}
							canMove={getCanMoveForIndex(index)}
							moveUp={() => moveItem(index, index - 1)}
							moveDown={() => moveItem(index, index + 1)}
							moveToTop={() => moveToTop(index)}
							moveToBottom={() => moveToBottom(index)}
						/>
					))}
				</SortableContext>
			</DndContext>

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
