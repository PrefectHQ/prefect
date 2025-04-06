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
};

export function SchemaFormInputArrayItem({
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
}: SchemaFormInputArrayItemProps) {
	const { schema } = useSchemaFormContext();
	const id = useId();

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
		<div className="grid grid-cols-[1fr_auto] gap-2">
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
					<DropdownMenuItem onClick={moveUp}>Move up</DropdownMenuItem>
				)}
				{canMove && !last && (
					<DropdownMenuItem onClick={moveDown}>Move down</DropdownMenuItem>
				)}
			</SchemaFormPropertyMenu>
		</div>
	);
}
