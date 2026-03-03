import { cn } from "@/utils";
import { Badge, type BadgeProps } from "./badge";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "./hover-card";
import { TagBadge } from "./tag-badge";

type TagBadgeGroupProps = {
	tags: string[] | undefined;
	variant?: BadgeProps["variant"];
	maxTagsDisplayed?: number;
	onTagsChange?: (tags: string[]) => void;
	clickable?: boolean;
};

export const TagBadgeGroup = ({
	tags = [],
	variant,
	maxTagsDisplayed = 2,
	onTagsChange,
	clickable,
}: TagBadgeGroupProps) => {
	const removeTag = (tag: string) => {
		onTagsChange?.(tags.filter((t) => t !== tag));
	};

	const numTags = tags.length;

	if (numTags > maxTagsDisplayed) {
		return (
			<HoverCard>
				<HoverCardTrigger asChild>
					<Badge
						variant={variant}
						className={cn(
							"ml-1 whitespace-nowrap",
							clickable &&
								"hover:bg-accent hover:text-accent-foreground cursor-pointer transition-colors",
						)}
					>
						{numTags} tags
					</Badge>
				</HoverCardTrigger>
				<HoverCardContent className="flex flex-wrap gap-1">
					{tags.map((tag) => (
						<TagBadge
							key={tag}
							tag={tag}
							onRemove={onTagsChange ? () => removeTag(tag) : undefined}
							clickable={clickable}
						/>
					))}
				</HoverCardContent>
			</HoverCard>
		);
	}

	return (
		<>
			{tags.map((tag) => (
				<TagBadge
					key={tag}
					tag={tag}
					onRemove={onTagsChange ? () => removeTag(tag) : undefined}
					variant={variant}
					clickable={clickable}
				/>
			))}
		</>
	);
};
