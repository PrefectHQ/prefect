import { useSuspenseQuery } from "@tanstack/react-query";
import { XIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { buildListFlowRunTagsQuery } from "@/api/flow-run-tags";
import { Badge } from "@/components/ui/badge";
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
import { cn } from "@/lib/utils";

export type FlowRunTagsInputProps = {
	value?: string[];
	onChange: (tags: string[]) => void;
	placeholder?: string;
	disabled?: boolean;
	className?: string;
};

export function FlowRunTagsInput({
	value = [],
	onChange,
	placeholder = "Filter by tags",
	disabled = false,
	className,
}: FlowRunTagsInputProps) {
	const [search, setSearch] = useState("");

	const { data: availableTags = [] } = useSuspenseQuery(
		buildListFlowRunTagsQuery(),
	);

	const filteredTags = useMemo(() => {
		if (!search) return availableTags.slice(0, 10);

		return availableTags
			.filter(
				(tag) =>
					tag.toLowerCase().includes(search.toLowerCase()) &&
					!value.includes(tag),
			)
			.slice(0, 10);
	}, [availableTags, search, value]);

	const handleTagSelect = (tag: string) => {
		if (!value.includes(tag)) {
			onChange([...value, tag]);
		}
		setSearch("");
	};

	const handleTagRemove = (tagToRemove: string) => {
		onChange(value.filter((tag) => tag !== tagToRemove));
	};

	const displayValue =
		value.length > 0
			? `${value.length} tag${value.length === 1 ? "" : "s"} selected`
			: placeholder;

	return (
		<div className={cn("space-y-2", className)}>
			<Combobox>
				<ComboboxTrigger aria-label="Select tags" selected={value.length === 0}>
					{displayValue}
				</ComboboxTrigger>
				<ComboboxContent>
					<ComboboxCommandInput
						value={search}
						onValueChange={setSearch}
						placeholder="Search tags..."
					/>
					<ComboboxCommandList>
						{filteredTags.length === 0 && (
							<ComboboxCommandEmtpy>
								{search ? "No tags found." : "No tags available."}
							</ComboboxCommandEmtpy>
						)}
						<ComboboxCommandGroup>
							{filteredTags.map((tag) => (
								<ComboboxCommandItem
									key={tag}
									value={tag}
									onSelect={handleTagSelect}
									closeOnSelect={false}
									selected={value.includes(tag)}
								>
									{tag}
								</ComboboxCommandItem>
							))}
							{search &&
								!filteredTags.includes(search) &&
								!value.includes(search) && (
									<ComboboxCommandItem
										value={search}
										onSelect={() => handleTagSelect(search)}
										closeOnSelect={false}
									>
										Create &quot;{search}&quot;
									</ComboboxCommandItem>
								)}
						</ComboboxCommandGroup>
					</ComboboxCommandList>
				</ComboboxContent>
			</Combobox>

			{value.length > 0 && (
				<div className="flex flex-wrap gap-1">
					{value.map((tag) => (
						<Badge key={tag} variant="secondary" className="text-xs">
							{tag}
							<button
								type="button"
								className="ml-1 rounded-full hover:bg-muted"
								onClick={() => handleTagRemove(tag)}
								disabled={disabled}
							>
								<XIcon className="h-3 w-3" />
								<span className="sr-only">Remove {tag} tag</span>
							</button>
						</Badge>
					))}
				</div>
			)}
		</div>
	);
}
