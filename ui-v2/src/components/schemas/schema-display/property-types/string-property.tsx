import type { PropertyRendererProps } from "../types";

export function StringProperty({ value, property }: PropertyRendererProps) {
	const displayValue = value ?? property.default ?? "";

	return (
		<span className="font-mono text-sm">
			{typeof displayValue === "string"
				? displayValue
				: JSON.stringify(displayValue)}
		</span>
	);
}
