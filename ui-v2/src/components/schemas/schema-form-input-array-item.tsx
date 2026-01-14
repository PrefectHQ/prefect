import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { useId, useMemo } from "react";
import { DropdownMenuItem } from "../ui/dropdown-menu";
import { SchemaFormInput } from "./schema-form-input";
import { SchemaFormPropertyErrors } from "./schema-form-property-errors";
import { SchemaFormPropertyMenu } from "./schema-form-property-menu";
import type { SchemaFormErrors } from "./types/errors";
import { useSchemaFormContext } from "./use-schema-form-context";
import { isArray, isReferenceObject } from "./utilities/guards";
import { getSchemaDefinition } from "./utilities/mergeSchemaPropertyDefinition";

export type SchemaFormInputArrayItemProps = {
	itemKey: string;
	items: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	value: unknown;
	onValueChange: (value: unknown) => void;
	errors: SchemaFormErrors;
	onDelete: () => void;
	first: boolean;
	last: boolean;
	canMove: boolean;
	moveUp: () => void;
	moveDown: () => void;
	moveToTop: () => void;
	moveToBottom: () => void;
};

export function SchemaFormInputArrayItem({
	itemKey,
	items,
	value,
	onValueChange,
	errors,
	onDelete,
	first,
	last,
	canMove,
	moveUp,
	moveDown,
	moveToTop,
	moveToBottom,
}: SchemaFormInputArrayItemProps) {
	const { schema } = useSchemaFormContext();
	const id = useId();

	const {
		attributes,
		listeners,
		setNodeRef,
		transform,
		transition,
		isDragging,
	} = useSortable({ id: itemKey, disabled: !canMove });

	const style = {
		transform: CSS.Transform.toString(transform),
		transition,
		opacity: isDragging ? 0.5 : 1,
	};

	const property = useMemo(() => {
		if (isArray(items)) {
			// @ts-expect-error The SchemaObject type requires a type property but in an anyOf property the type comes from the anyOf property
			const property: SchemaObject = {
				anyOf: items,
			};

			return property;
		}

		if (isReferenceObject(items)) {
			return getSchemaDefinition(schema, items.$ref);
		}

		return items;
	}, [items, schema]);

	return (
		<div
			ref={setNodeRef}
			style={style}
			className="grid grid-cols-[auto_1fr_auto] gap-2"
		>
			{canMove ? (
				<button
					type="button"
					className="flex items-center justify-center cursor-grab text-muted-foreground hover:text-foreground focus:outline-none"
					aria-label="Drag to reorder"
					{...attributes}
					{...listeners}
				>
					<GripVertical className="h-5 w-5" />
				</button>
			) : (
				<div className="w-5" />
			)}
			<div className="grid grid-cols-1 gap-2">
				<SchemaFormInput
					value={value}
					onValueChange={onValueChange}
					property={property}
					errors={errors}
					id={id}
				/>
				<SchemaFormPropertyErrors errors={errors} />
			</div>
			<SchemaFormPropertyMenu
				value={value}
				onValueChange={onValueChange}
				property={items}
			>
				<DropdownMenuItem onClick={onDelete}>Delete</DropdownMenuItem>
				{canMove && !first && (
					<>
						<DropdownMenuItem onClick={moveToTop}>Move to top</DropdownMenuItem>
						<DropdownMenuItem onClick={moveUp}>Move up</DropdownMenuItem>
					</>
				)}
				{canMove && !last && (
					<>
						<DropdownMenuItem onClick={moveDown}>Move down</DropdownMenuItem>
						<DropdownMenuItem onClick={moveToBottom}>
							Move to bottom
						</DropdownMenuItem>
					</>
				)}
			</SchemaFormPropertyMenu>
		</div>
	);
}
