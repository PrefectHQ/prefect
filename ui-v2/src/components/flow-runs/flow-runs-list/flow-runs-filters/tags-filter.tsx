import { useQuery } from "@tanstack/react-query";
import {
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useState,
} from "react";
import { toast } from "sonner";
import { buildPaginateFlowRunsQuery } from "@/api/flow-runs";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Skeleton } from "@/components/ui/skeleton";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { Typography } from "@/components/ui/typography";

const MAX_TAGS_DISPLAYED = 2;

type TagsFilterProps = {
	selectedTags: Set<string>;
	onSelectTags: (tags: Set<string>) => void;
};

export const TagsFilter = ({ selectedTags, onSelectTags }: TagsFilterProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data, isLoading, isError } = useQuery(
		buildPaginateFlowRunsQuery({
			page: 1,
			limit: 100,
			sort: "START_TIME_DESC",
		}),
	);

	useEffect(() => {
		if (isError) {
			toast.error("Failed to load tag suggestions");
		}
	}, [isError]);

	const suggestions = useMemo(() => {
		const all = new Set<string>();
		(data?.results ?? []).forEach((fr) => {
			(fr.tags ?? []).forEach((t) => {
				all.add(t);
			});
		});
		return Array.from(all).sort((a, b) => a.localeCompare(b));
	}, [data?.results]);

	const handleSelectTag = (tag: string) => {
		const updatedTags = new Set(selectedTags);
		if (selectedTags.has(tag)) {
			updatedTags.delete(tag);
		} else {
			updatedTags.add(tag);
		}
		onSelectTags(updatedTags);
	};

	const handleClearAll = () => {
		onSelectTags(new Set());
	};

	const addFreeformTag = useCallback(
		(tag: string) => {
			const trimmed = tag.trim();
			if (!trimmed) return;
			const lowerTrimmed = trimmed.toLowerCase();
			const alreadyExists = Array.from(selectedTags).some(
				(t) => t.toLowerCase() === lowerTrimmed,
			);
			if (alreadyExists) return;
			const updatedTags = new Set(selectedTags);
			updatedTags.add(trimmed);
			onSelectTags(updatedTags);
		},
		[onSelectTags, selectedTags],
	);

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

	const renderSelectedTags = () => {
		if (selectedTags.size === 0) {
			return "All tags";
		}

		const selected = Array.from(selectedTags);

		if (selected.length > MAX_TAGS_DISPLAYED) {
			return (
				<div className="flex flex-1 min-w-0 items-center gap-2">
					<TagBadgeGroup
						tags={selected}
						variant="secondary"
						maxTagsDisplayed={MAX_TAGS_DISPLAYED}
					/>
				</div>
			);
		}

		const extraCount = selected.length - MAX_TAGS_DISPLAYED;

		return (
			<div className="flex flex-1 min-w-0 items-center gap-2">
				<div className="flex flex-1 min-w-0 items-center gap-2 overflow-hidden">
					<TagBadgeGroup
						tags={selected.slice(0, MAX_TAGS_DISPLAYED)}
						variant="secondary"
						maxTagsDisplayed={MAX_TAGS_DISPLAYED}
					/>
				</div>
				{extraCount > 0 && (
					<Typography variant="bodySmall" className="shrink-0">
						+ {extraCount}
					</Typography>
				)}
			</div>
		);
	};

	const filteredSuggestions = useMemo(() => {
		return suggestions
			.filter((tag) => !selectedTags.has(tag))
			.filter((tag) => {
				const q = deferredSearch.trim().toLowerCase();
				if (!q) return true;
				return tag.toLowerCase().includes(q);
			});
	}, [suggestions, selectedTags, deferredSearch]);

	const searchTrimmed = search.trim();
	const searchLower = searchTrimmed.toLowerCase();
	const canAddFreeform =
		searchTrimmed &&
		!Array.from(selectedTags).some((t) => t.toLowerCase() === searchLower) &&
		!suggestions.some((t) => t.toLowerCase() === searchLower);

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by tag"
				selected={selectedTags.size === 0}
			>
				{renderSelectedTags()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search or enter new tag"
					onKeyDown={(e) => {
						const query = search.trim();
						if (e.key === "Enter" && query && canAddFreeform) {
							e.preventDefault();
							addFreeformTag(query);
							setSearch("");
						}
					}}
				/>
				<ComboboxCommandList>
					{isLoading ? (
						<div className="p-2 space-y-2">
							<Skeleton className="h-6 w-full" />
							<Skeleton className="h-6 w-full" />
							<Skeleton className="h-6 w-full" />
						</div>
					) : (
						<>
							{filteredSuggestions.length === 0 &&
								!canAddFreeform &&
								selectedTags.size === 0 && (
									<ComboboxCommandEmtpy>No matching tags</ComboboxCommandEmtpy>
								)}
							<ComboboxCommandGroup>
								<ComboboxCommandItem
									aria-label="All tags"
									onSelect={handleClearAll}
									closeOnSelect={false}
									value="__all__"
								>
									<Checkbox checked={selectedTags.size === 0} />
									All tags
								</ComboboxCommandItem>

								{Array.from(selectedTags).map((tag) => (
									<ComboboxCommandItem
										key={`selected-${tag}`}
										aria-label={tag}
										onSelect={() => handleSelectTag(tag)}
										closeOnSelect={false}
										value={`selected-${tag}`}
									>
										<Checkbox checked={true} />
										{tag}
									</ComboboxCommandItem>
								))}

								{canAddFreeform && (
									<ComboboxCommandItem
										value={`__add__:${searchTrimmed}`}
										onSelect={() => {
											addFreeformTag(searchTrimmed);
											setSearch("");
										}}
										closeOnSelect={false}
									>
										Add &quot;{searchTrimmed}&quot;
									</ComboboxCommandItem>
								)}

								{filteredSuggestions.map((tag) => (
									<ComboboxCommandItem
										key={tag}
										aria-label={tag}
										onSelect={() => handleSelectTag(tag)}
										closeOnSelect={false}
										value={tag}
									>
										<Checkbox checked={false} />
										{tag}
									</ComboboxCommandItem>
								))}
							</ComboboxCommandGroup>
						</>
					)}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
