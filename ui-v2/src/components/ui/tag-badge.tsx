import { Icon } from "@/components/ui/icons";
import { cn } from "@/utils";
import { Badge, type BadgeProps } from "./badge";

type TagBadgeProps = {
	tag: string;
	variant?: BadgeProps["variant"];
	onRemove?: () => void;
	clickable?: boolean;
};

export const TagBadge = ({
	tag,
	variant,
	onRemove,
	clickable,
}: TagBadgeProps) => {
	return (
		<Badge
			variant={variant}
			className={cn(
				"ml-1 max-w-20",
				clickable &&
					"hover:bg-accent hover:text-accent-foreground cursor-pointer transition-colors",
			)}
			title={tag}
		>
			<span className="truncate">{tag}</span>
			{onRemove && (
				<button
					type="button"
					onClick={onRemove}
					className="text-muted-foreground hover:text-foreground rounded-sm focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
					aria-label={`Remove ${tag} tag`}
				>
					<Icon id="X" size={14} />
				</button>
			)}
		</Badge>
	);
};
