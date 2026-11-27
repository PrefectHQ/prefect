import type { SchemaObject } from "openapi-typescript";
import { useMemo, useState } from "react";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "../ui/combobox";
import { TagBadge } from "../ui/tag-badge";
import type { PrimitiveProperty } from "./types/primitives";
import type { WithPrimitiveEnum } from "./types/schemas";

type SingleValueProps<T extends PrimitiveProperty> = {
	value: T | undefined;
	multiple: false;
	onValueChange: (value: T | undefined) => void;
};

type MultipleValueProps<T extends PrimitiveProperty> = {
	values: T[] | undefined;
	multiple: true;
	onValuesChange: (values: T[] | undefined) => void;
};

type SchemaFormInputArrayComboboxProps<T extends PrimitiveProperty> = {
	property: SchemaObject & WithPrimitiveEnum;
	id: string;
} & (SingleValueProps<T> | MultipleValueProps<T>);

export function SchemaFormInputEnum<T extends PrimitiveProperty>({
	property,
	id,
	...props
}: SchemaFormInputArrayComboboxProps<T>) {
	const [search, setSearch] = useState("");

	const getLabel = useMemo(() => {
		const names: unknown = property["x-enum-varnames"];
		const labels =
			Array.isArray(names) &&
			names.length === property.enum.length &&
			names.every((name) => typeof name === "string")
				? names
				: undefined;

		return (value: PrimitiveProperty | undefined): string => {
			const index =
				labels && value !== undefined ? property.enum.indexOf(value) : -1;

			return labels && index !== -1 ? labels[index] : String(value);
		};
	}, [property]);

	const options = useMemo(() => {
		return Object.fromEntries(
			Object.entries(property.enum).filter(([, value]) =>
				getLabel(value).toLowerCase().includes(search.toLowerCase()),
			),
		);
	}, [property.enum, getLabel, search]);

	const selected = props.multiple
		? Boolean(props.values?.length)
		: props.value !== undefined;
	const label = props.multiple
		? props.values?.map(getLabel).join(", ")
		: getLabel(props.value);

	function isSelected(key: string) {
		const value = options[key] as T;

		return props.multiple
			? props.values?.includes(value)
			: props.value === value;
	}

	function onSelect(key: string) {
		setSearch("");

		const value = options[key] as T;

		return props.multiple ? onSelectMultiple(value) : onSelectSingle(value);
	}

	function onSelectSingle(value: T) {
		if (props.multiple) {
			throw new Error("onSingleSelect called on multiple value input");
		}

		props.onValueChange(value);
	}

	function onSelectMultiple(value: T) {
		if (!props.multiple) {
			throw new Error("onMultipleSelect called on single value input");
		}

		if (!props.values) {
			props.onValuesChange([value]);
			return;
		}

		if (props.values?.includes(value)) {
			props.onValuesChange(props.values.filter((v) => v !== value));
			return;
		}

		props.onValuesChange([...props.values, value]);
	}

	return (
		<div className="flex flex-col gap-1">
			<Combobox>
				<ComboboxTrigger
					selected={selected && !props.multiple}
					aria-label={`Select ${property.title}`}
					id={id}
				>
					{selected && !props.multiple ? label : "Select"}
				</ComboboxTrigger>
				<ComboboxContent>
					<ComboboxCommandInput
						value={search}
						onValueChange={setSearch}
						placeholder="Search..."
					/>
					<ComboboxCommandEmtpy>No values found</ComboboxCommandEmtpy>
					<ComboboxCommandList>
						{Object.entries(options).map(([index, value]) => (
							<ComboboxCommandItem
								key={index}
								value={index}
								onSelect={onSelect}
								selected={isSelected(index)}
								closeOnSelect={!props.multiple}
							>
								{getLabel(value)}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandList>
				</ComboboxContent>
			</Combobox>
			{props.multiple && props.values && props.values.length > 0 && (
				<div className="flex flex-wrap gap-1">
					{props.values.map((value) => (
						<TagBadge
							key={String(value)}
							tag={getLabel(value)}
							onRemove={() => onSelectMultiple(value)}
						/>
					))}
				</div>
			)}
		</div>
	);
}
