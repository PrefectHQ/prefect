import { Icon } from "@/components/ui/icons";
import { cn } from "@/utils";
import { Badge, type BadgeProps } from "./badge";

type TagBadgeProps = {
	tag: string;
	variant?: BadgeProps["variant"];
	onRemove?: () => void;
	className?: string;
};

export const TagBadge = ({
	tag,
	variant,
	onRemove,
	className,
}: TagBadgeProps) => {
	return (
		<Badge variant={variant} className={cn("ml-1", className)} title={tag}>
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
