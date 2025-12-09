import { X } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";

type TagsInputProps = {
	selectedTags: string[];
	onSelectTags: (tags: string[]) => void;
};

export const TagsInput = ({ selectedTags, onSelectTags }: TagsInputProps) => {
	const [open, setOpen] = useState(false);
	const [inputValue, setInputValue] = useState("");

	const handleAddTag = () => {
		const trimmedValue = inputValue.trim();
		if (trimmedValue && !selectedTags.includes(trimmedValue)) {
			onSelectTags([...selectedTags, trimmedValue]);
			setInputValue("");
		}
	};

	const handleRemoveTag = (tagToRemove: string) => {
		onSelectTags(selectedTags.filter((tag) => tag !== tagToRemove));
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter") {
			e.preventDefault();
			handleAddTag();
		}
	};

	const getDisplayText = () => {
		if (selectedTags.length === 0) {
			return "All tags";
		}
		if (selectedTags.length === 1) {
			return selectedTags[0];
		}
		return `${selectedTags.length} tags`;
	};

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					className="w-full justify-between"
					aria-label="Filter by tags"
				>
					<span className="truncate">{getDisplayText()}</span>
					<Icon id="ChevronDown" className="ml-2 size-4 shrink-0" />
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-64 p-3" align="start">
				<div className="flex flex-col gap-3">
					<div className="flex gap-2">
						<Input
							placeholder="Add tag..."
							value={inputValue}
							onChange={(e) => setInputValue(e.target.value)}
							onKeyDown={handleKeyDown}
							className="h-8"
						/>
						<Button
							size="sm"
							onClick={handleAddTag}
							disabled={!inputValue.trim()}
						>
							Add
						</Button>
					</div>
					{selectedTags.length > 0 && (
						<div className="flex flex-wrap gap-1">
							{selectedTags.map((tag) => (
								<Badge
									key={tag}
									variant="secondary"
									className="flex items-center gap-1"
								>
									{tag}
									<button
										type="button"
										onClick={() => handleRemoveTag(tag)}
										className="ml-1 rounded-full hover:bg-muted"
									>
										<X className="size-3" />
									</button>
								</Badge>
							))}
						</div>
					)}
				</div>
			</PopoverContent>
		</Popover>
	);
};
