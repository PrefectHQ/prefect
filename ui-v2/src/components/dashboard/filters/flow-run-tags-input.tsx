import { useMemo, useState } from "react";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";
import { TagsInput } from "@/components/ui/tags-input";

export type FlowRunTagsInputProps = {
	value?: string[];
	onChange?: (tags: string[]) => void;
	availableTags?: string[];
	placeholder?: string;
};

export const FlowRunTagsInput = ({
	value = [],
	onChange,
	availableTags = [],
	placeholder = "Add tags",
}: FlowRunTagsInputProps) => {
	const [searchValue, setSearchValue] = useState("");

	// Filter available tags based on search and exclude already selected tags
	const filteredTags = useMemo(() => {
		return availableTags
			.filter((tag) => !value.includes(tag))
			.filter((tag) =>
				searchValue
					? tag.toLowerCase().includes(searchValue.toLowerCase())
					: true,
			);
	}, [availableTags, value, searchValue]);

	const handleTagSelect = (tag: string) => {
		if (!value.includes(tag)) {
			onChange?.([...value, tag]);
		}
		setSearchValue("");
	};

	const selectedTagsDisplay =
		value.length > 0
			? `${value.length} tag${value.length === 1 ? "" : "s"} selected`
			: placeholder;

	// Cast to properly handle TagsInput prop types
	const tagsInputProps = {
		value,
		onChange,
		placeholder: "Selected tags",
	} as Parameters<typeof TagsInput>[0];

	return (
		<div className="space-y-2">
			{/* Display current tags */}
			{value.length > 0 && <TagsInput {...tagsInputProps} />}

			{/* Combobox for adding new tags */}
			<Combobox>
				<ComboboxTrigger aria-label="Select tags">
					{selectedTagsDisplay}
				</ComboboxTrigger>
				<ComboboxContent>
					<ComboboxCommandInput
						value={searchValue}
						onValueChange={setSearchValue}
						placeholder="Search tags..."
					/>
					<ComboboxCommandList>
						<ComboboxCommandEmtpy>
							{searchValue ? (
								<div className="py-6 text-center text-sm">
									<p>No tags found</p>
									<p className="text-xs text-muted-foreground mt-1">
										Try typing to add a new tag
									</p>
								</div>
							) : (
								"No tags available"
							)}
						</ComboboxCommandEmtpy>
						<ComboboxCommandGroup>
							{/* Add option for custom tag if searching */}
							{searchValue &&
								!filteredTags.some(
									(tag) => tag.toLowerCase() === searchValue.toLowerCase(),
								) &&
								!value.some(
									(tag) => tag.toLowerCase() === searchValue.toLowerCase(),
								) && (
									<ComboboxCommandItem
										value={searchValue}
										onSelect={() => handleTagSelect(searchValue)}
										closeOnSelect={false}
									>
										Add "{searchValue}"
									</ComboboxCommandItem>
								)}

							{/* Available tags */}
							{filteredTags.map((tag) => (
								<ComboboxCommandItem
									key={tag}
									value={tag}
									onSelect={() => handleTagSelect(tag)}
									closeOnSelect={false}
								>
									{tag}
								</ComboboxCommandItem>
							))}
						</ComboboxCommandGroup>
					</ComboboxCommandList>
				</ComboboxContent>
			</Combobox>
		</div>
	);
};
