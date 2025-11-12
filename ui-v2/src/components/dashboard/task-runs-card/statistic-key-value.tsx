import { cn } from "@/utils";

type StatisticKeyValueProps = {
	value: string | number;
	label?: string;
	meta?: string;
	primary?: boolean;
	className?: string;
};

export const StatisticKeyValue = ({
	value,
	label,
	meta,
	primary = false,
	className,
}: StatisticKeyValueProps) => {
	const formattedValue =
		typeof value === "number" ? value.toLocaleString() : value;

	return (
		<div
			className={cn(
				"inline-flex items-end gap-1 text-sm",
				primary && "text-base",
				className,
			)}
		>
			<span className="font-semibold">{formattedValue}</span>
			{label && <span>{label}</span>}
			{meta && <span className="text-muted-foreground">{meta}</span>}
		</div>
	);
};
