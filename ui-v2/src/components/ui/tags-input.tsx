import type { ChangeEvent, FocusEvent, KeyboardEvent } from "react";
import { useState } from "react";
import { Input, type InputProps } from "@/components/ui/input";
import { TagBadgeGroup } from "./tag-badge-group";

export type TagsInputProps = InputProps & {
	value?: string[];
	onChange?: (tags: string[]) => void;
	placeholder?: string;
};

export const TagsInput = ({
	onChange,
	value = [],
	onBlur,
	placeholder = "Enter tags",
	...props
}: TagsInputProps = {}) => {
	const [inputValue, setInputValue] = useState("");

	const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
		setInputValue(e.target.value);
	};

	const handleInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter" && inputValue.trim() !== "") {
			e.preventDefault();
			addTag(inputValue.trim());
		} else if (e.key === "Backspace" && inputValue === "" && value.length > 0) {
			removeTag(value.length - 1);
		}
	};

	const handleInputBlur =
		(childOnBlur?: (e: FocusEvent<HTMLInputElement>) => void) =>
		(e: FocusEvent<HTMLInputElement>) => {
			if (inputValue.trim() !== "") {
				addTag(inputValue.trim());
			}
			childOnBlur?.(e);
		};

	const addTag = (tag: string) => {
		if (!value.includes(tag)) {
			const newTags = [...value, tag];
			setInputValue("");
			onChange?.(newTags);
		}
	};

	const removeTag = (index: number) => {
		const newTags = value.filter((_, i) => i !== index);
		onChange?.(newTags);
	};

	return (
		<div className="flex items-center border rounded-md focus-within:ring-1 focus-within:ring-ring ">
			<TagBadgeGroup tags={value} onTagsChange={onChange} variant="secondary" />
			<Input
				type="text"
				value={inputValue}
				onChange={handleInputChange}
				onKeyDown={handleInputKeyDown}
				onBlur={handleInputBlur(onBlur)}
				className="grow border-none shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
				placeholder={placeholder}
				aria-label={placeholder}
				{...props}
			/>
		</div>
	);
};
