import React from "react";
import { useState } from "react";
import type { KeyboardEvent, ChangeEvent, FocusEvent } from "react";
import { Input, type InputProps } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

type TagsInputProps = InputProps & {
	value?: string[];
	onChange?: (tags: string[]) => void;
};

const TagsInput = React.forwardRef<HTMLInputElement, TagsInputProps>(
	({ onChange, value = [], onBlur, ...props }: TagsInputProps = {}) => {
		const [inputValue, setInputValue] = useState("");

		const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
			setInputValue(e.target.value);
		};

		const handleInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
			if (e.key === "Enter" && inputValue.trim() !== "") {
				e.preventDefault();
				addTag(inputValue.trim());
			} else if (
				e.key === "Backspace" &&
				inputValue === "" &&
				value.length > 0
			) {
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
			<div className="flex flex-wrap items-center border rounded-md focus-within:ring-1 focus-within:ring-ring ">
				<div className="flex flex-wrap items-center gap-2 px-2">
					{value.map((tag, index) => (
						<Badge key={tag} variant="secondary" className="gap-1 px-2 mt-2">
							{tag}
							<button
								type="button"
								onClick={() => removeTag(index)}
								className="text-muted-foreground hover:text-foreground"
								aria-label={`Remove ${tag} tag`}
							>
								<X size={14} />
							</button>
						</Badge>
					))}
				</div>
				<Input
					type="text"
					value={inputValue}
					onChange={handleInputChange}
					onKeyDown={handleInputKeyDown}
					onBlur={handleInputBlur(onBlur)}
					className="flex-grow border-none shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
					placeholder="Enter tags"
					aria-label="Enter tags"
					{...props}
				/>
			</div>
		);
	},
);

TagsInput.displayName = "TagsInput";

export { TagsInput };
