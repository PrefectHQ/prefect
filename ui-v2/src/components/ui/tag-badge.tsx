import { Icon } from "@/components/ui/icons";
import { Badge, type BadgeProps } from "./badge";

type TagBadgeProps = {
	tag: string;
	variant?: BadgeProps["variant"];
	onRemove?: () => void;
};

export const TagBadge = ({ tag, variant, onRemove }: TagBadgeProps) => {
	return (
		<Badge variant={variant} className="ml-1 max-w-20" title={tag}>
			<span className="truncate">{tag}</span>
			{onRemove && (
				<button
					type="button"
					onClick={onRemove}
					className="text-muted-foreground hover:text-foreground"
					aria-label={`Remove ${tag} tag`}
				>
					<Icon id="X" size={14} />
				</button>
			)}
		</Badge>
	);
};
