import { cn } from "@/lib/utils";

export type KeyValueItem = {
	key: string;
	value: React.ReactNode;
	hidden?: boolean;
};

export type KeyValueDisplayProps = {
	items: KeyValueItem[];
	className?: string;
	variant?: "default" | "compact";
};

export function KeyValueDisplay({
	items,
	className,
	variant = "default",
}: KeyValueDisplayProps) {
	const visibleItems = items.filter((item) => !item.hidden);

	const spacing = variant === "compact" ? "space-y-2" : "space-y-4";
	const gridSpacing = variant === "compact" ? "gap-2" : "gap-4";

	return (
		<div className={cn(spacing, className)}>
			<div
				className={cn(
					"grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
					gridSpacing,
				)}
			>
				{visibleItems.map(({ key, value }) => (
					<div key={key} className="space-y-1">
						<dt className="text-sm font-medium text-muted-foreground">{key}</dt>
						<dd className="text-sm">{value}</dd>
					</div>
				))}
			</div>
		</div>
	);
}
