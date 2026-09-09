import { useCallback, useEffect, useState } from "react";
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
import { Icon } from "@/components/ui/icons";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";

export type TagsSelectProps = {
	suggestions: string[];
	value?: string[];
	onChange?: (tags: string[]) => void;
	placeholder?: string;
	"aria-label"?: string;
	id?: string;
};

/**
 * Combobox that selects tags from a list of suggestions and also accepts
 * freeform tags. Callers provide the suggestions.
 */
export function TagsSelect({
	suggestions,
	value = [],
	onChange,
	placeholder = "All tags",
	"aria-label": ariaLabel = "Tags",
	id,
}: TagsSelectProps) {
	const [search, setSearch] = useState("");

	const toggleTag = (tag: string) => {
		const exists = value.includes(tag);
		const next = exists ? value.filter((t) => t !== tag) : [...value, tag];
		onChange?.(next);
	};

	const addFreeformTag = useCallback(
		(tag: string) => {
			if (!tag) return;
			if (value.includes(tag)) return;
			onChange?.([...value, tag]);
		},
		[onChange, value],
	);

	// Add on trailing comma for quick entry (matches common tags UX)
	useEffect(() => {
		const trimmed = search.trim();
		if (trimmed.endsWith(",")) {
			const tag = trimmed.replace(/,+$/, "").trim();
			if (tag) {
				addFreeformTag(tag);
			}
			setSearch("");
		}
	}, [search, addFreeformTag]);

	return (
		<div className="w-full">
			<Combobox>
				<ComboboxTrigger
					aria-label={ariaLabel}
					id={id}
					selected={value.length === 0}
				>
					{value.length > 0 ? (
						<div className="flex items-center gap-1 overflow-hidden">
							<TagBadgeGroup
								tags={value}
								variant="secondary"
								maxTagsDisplayed={3}
							/>
						</div>
					) : (
						<span className="text-muted-foreground">{placeholder}</span>
					)}
				</ComboboxTrigger>
				<ComboboxContent>
					<ComboboxCommandInput
						value={search}
						onValueChange={setSearch}
						placeholder="Search or enter new tag"
						onKeyDown={(e) => {
							const query = search.trim();
							if (e.key === "Enter" && query) {
								e.preventDefault();
								addFreeformTag(query);
								setSearch("");
							} else if (e.key === "Backspace" && !search && value.length > 0) {
								onChange?.(value.slice(0, -1));
							}
						}}
					/>
					<ComboboxCommandList>
						{suggestions.length > 0 ? (
							<ComboboxCommandEmtpy>No tags found</ComboboxCommandEmtpy>
						) : null}
						<ComboboxCommandGroup>
							{/* Selected tags with inline remove */}
							{value.length > 0 && (
								<div>
									{value.map((tag) => (
										<ComboboxCommandItem
											key={`selected-${tag}`}
											value={`selected-${tag}`}
											onSelect={() => toggleTag(tag)}
											closeOnSelect={false}
										>
											<button
												type="button"
												aria-label={`Remove ${tag} tag`}
												className="text-muted-foreground hover:text-foreground"
												onClick={(ev) => {
													ev.preventDefault();
													ev.stopPropagation();
													onChange?.(value.filter((t) => t !== tag));
												}}
											>
												<Icon id="X" className="size-3" />
											</button>
											<span>{tag}</span>
										</ComboboxCommandItem>
									))}
									<ComboboxCommandItem
										value="__clear__"
										onSelect={() => onChange?.([])}
										closeOnSelect={false}
									>
										Clear all tags
									</ComboboxCommandItem>
								</div>
							)}

							{/* Add freeform */}
							{search.trim() && !value.includes(search.trim()) && (
								<ComboboxCommandItem
									value={`__add__:${search.trim()}`}
									onSelect={() => addFreeformTag(search.trim())}
									closeOnSelect={false}
								>
									Add &quot;{search.trim()}&quot;
								</ComboboxCommandItem>
							)}

							{/* Suggestions (exclude already selected) */}
							{suggestions
								.filter((t) => !value.includes(t))
								.filter((t) => {
									const q = search.trim().toLowerCase();
									if (!q) return true;
									return t.toLowerCase().includes(q);
								})
								.map((tag) => (
									<ComboboxCommandItem
										key={tag}
										value={tag}
										selected={value.includes(tag)}
										onSelect={() => toggleTag(tag)}
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
}

TagsSelect.displayName = "TagsSelect";
