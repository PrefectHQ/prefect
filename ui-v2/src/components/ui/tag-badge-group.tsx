import { useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/utils";
import { Badge, type BadgeProps } from "./badge";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { TagBadge } from "./tag-badge";

type TagBadgeGroupProps = {
	tags: string[] | undefined;
	variant?: BadgeProps["variant"];
	/**
	 * Hard cap on the number of tags shown inline. Tags beyond the cap are
	 * moved into the overflow popover even when there is room for them. By
	 * default the group shows as many tags as fit in its container.
	 */
	maxTagsDisplayed?: number;
	onTagsChange?: (tags: string[]) => void;
	onTagClick?: (tag: string) => void;
	/**
	 * Applied to each inline `TagBadge`. Use to opt into a width cap in
	 * tight layouts (e.g. `className="max-w-32"` inside a narrow table
	 * column); by default tags size to their content.
	 */
	tagClassName?: string;
	/**
	 * `popover` (default) renders the `+N` summary as a button that opens the
	 * hidden tags. Use `badge` when the group is rendered inside another
	 * interactive element (e.g. a combobox trigger), where a nested button is
	 * invalid; the hidden tag names are then exposed through `title`/`aria-label`.
	 */
	overflow?: "popover" | "badge";
};

/**
 * Tags that do not fit stay in the DOM on a zero-height, clipped second row
 * so their widths can be measured and so the container's max-content width
 * still reflects every tag; that lets the group grow back when the parent
 * gets wider.
 */
export const TagBadgeGroup = ({
	tags = [],
	variant,
	maxTagsDisplayed,
	onTagsChange,
	onTagClick,
	tagClassName,
	overflow: overflowMode = "popover",
}: TagBadgeGroupProps) => {
	const containerRef = useRef<HTMLDivElement>(null);
	const overflowSizerRef = useRef<HTMLSpanElement>(null);
	const tagRefs = useRef(new Map<number, HTMLSpanElement>());
	const [visibleCount, setVisibleCount] = useState(tags.length);

	const cap = Math.min(tags.length, maxTagsDisplayed ?? tags.length);

	useLayoutEffect(() => {
		const container = containerRef.current;
		if (!container) {
			return;
		}

		const measure = () => {
			const available = container.clientWidth;
			if (available <= 0) {
				setVisibleCount(cap);
				return;
			}
			const overflowWidth = overflowSizerRef.current?.offsetWidth ?? 0;
			let used = 0;
			let count = 0;
			for (let i = 0; i < cap; i++) {
				const width = tagRefs.current.get(i)?.offsetWidth ?? 0;
				const hasOverflow = i + 1 < tags.length;
				const needed = used + width + (hasOverflow ? overflowWidth : 0);
				if (needed > available) {
					break;
				}
				used += width;
				count = i + 1;
			}
			setVisibleCount(count);
		};

		measure();
		const resizeObserver = new ResizeObserver(measure);
		resizeObserver.observe(container);
		return () => resizeObserver.disconnect();
	}, [tags, cap]);

	const removeTag = (tag: string) => {
		onTagsChange?.(tags.filter((t) => t !== tag));
	};

	if (tags.length === 0) {
		return null;
	}

	const renderTag = ({ tag, key }: TagEntry) => (
		<TagBadge
			key={key}
			tag={tag}
			onRemove={onTagsChange ? () => removeTag(tag) : undefined}
			onClick={onTagClick ? () => onTagClick(tag) : undefined}
			variant={variant}
			className={tagClassName}
		/>
	);

	const renderMeasuredTag = (entry: TagEntry, hidden: boolean) => (
		<span
			key={entry.key}
			ref={(node) => setTagRef(tagRefs.current, entry.index, node)}
			data-slot="tag-badge-group-item"
			className={cn("inline-flex", hidden && hiddenItemClassName)}
			inert={hidden}
			aria-hidden={hidden}
		>
			{renderTag(entry)}
		</span>
	);

	const entries = toTagEntries(tags);
	const count = Math.min(visibleCount, cap);
	const visibleTags = entries.slice(0, count);
	const hiddenTags = entries.slice(count);
	const hasOverflow = hiddenTags.length > 0;

	const hiddenTagNames = hiddenTags.map((entry) => entry.tag).join(", ");

	const overflowClassName = "ml-1 tabular-nums";

	// Measures the widest possible counter (every tag hidden) so the fit
	// calculation never reserves less room than the rendered `+N` needs.
	const overflowSizer = (
		<span
			ref={overflowSizerRef}
			data-slot="tag-badge-group-overflow-sizer"
			className={cn("inline-flex", hiddenItemClassName)}
			inert
			aria-hidden
		>
			<Badge variant={variant} className={overflowClassName}>
				+{tags.length}
			</Badge>
		</span>
	);

	const overflow = (
		<span data-slot="tag-badge-group-overflow" className="inline-flex">
			{overflowMode === "badge" ? (
				<Badge
					variant={variant}
					className={overflowClassName}
					title={hiddenTagNames}
					aria-label={`${hiddenTags.length} more tags: ${hiddenTagNames}`}
				>
					+{hiddenTags.length}
				</Badge>
			) : (
				<Popover>
					<PopoverTrigger asChild>
						<Badge
							asChild
							variant={variant}
							className={cn(overflowClassName, "cursor-pointer")}
						>
							<button
								type="button"
								aria-label={`Show ${hiddenTags.length} more tags`}
								title={hiddenTagNames}
							>
								+{hiddenTags.length}
							</button>
						</Badge>
					</PopoverTrigger>
					<PopoverContent
						align="start"
						className="flex flex-wrap gap-1 w-auto max-w-72 p-2"
					>
						{hiddenTags.map(renderTag)}
					</PopoverContent>
				</Popover>
			)}
		</span>
	);

	return (
		<div
			ref={containerRef}
			data-slot="tag-badge-group"
			className="flex flex-wrap items-center min-w-0 max-w-full overflow-hidden"
		>
			{visibleTags.map((entry) => renderMeasuredTag(entry, false))}
			{hasOverflow && overflow}
			<span className="basis-full" aria-hidden />
			{hiddenTags.map((entry) => renderMeasuredTag(entry, true))}
			{overflowSizer}
		</div>
	);
};

const hiddenItemClassName = "h-0 overflow-hidden invisible";

type TagEntry = { tag: string; key: string; index: number };

/**
 * Gives repeated tag values distinct keys. The occurrence number is a prefix
 * ending at the first `:`, so a key decodes unambiguously and a literal tag
 * such as `1:alpha` cannot collide with the second `alpha`.
 */
function toTagEntries(tags: string[]): TagEntry[] {
	const seen = new Map<string, number>();
	return tags.map((tag, index) => {
		const occurrence = seen.get(tag) ?? 0;
		seen.set(tag, occurrence + 1);
		return { tag, key: `${occurrence}:${tag}`, index };
	});
}

function setTagRef(
	refs: Map<number, HTMLSpanElement>,
	index: number,
	node: HTMLSpanElement | null,
) {
	if (node) {
		refs.set(index, node);
	} else {
		refs.delete(index);
	}
}
