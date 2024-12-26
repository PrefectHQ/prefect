import { Badge, type BadgeProps } from "./badge";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "./hover-card";
import { TagBadge } from "./tag-badge";

type TagBadgeGroupProps = {
	tags: string[] | undefined;
	variant?: BadgeProps["variant"];
	maxTagsDisplayed?: number;
	onTagsChange?: (tags: string[]) => void;
};

export const TagBadgeGroup = ({
	tags = [],
	variant,
	maxTagsDisplayed = 2,
	onTagsChange,
}: TagBadgeGroupProps) => {
	const removeTag = (tag: string) => {
		onTagsChange?.(tags.filter((t) => t !== tag));
	};

	const numTags = tags.length;

	if (numTags > maxTagsDisplayed) {
		return (
			<HoverCard>
				<HoverCardTrigger asChild>
					<Badge variant={variant} className="ml-1 whitespace-nowrap">
						{numTags} tags
					</Badge>
				</HoverCardTrigger>
				<HoverCardContent className="flex flex-wrap gap-1">
					{tags.map((tag) => (
						<TagBadge
							key={tag}
							tag={tag}
							onRemove={onTagsChange ? () => removeTag(tag) : undefined}
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
				/>
			))}
		</>
	);
};
