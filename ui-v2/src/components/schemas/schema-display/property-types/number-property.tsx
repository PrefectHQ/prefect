import type { PropertyRendererProps } from "../types";

export function NumberProperty({ value, property }: PropertyRendererProps) {
	const displayValue = value ?? property.default ?? 0;

	return (
		<span className="font-mono text-sm">
			{typeof displayValue === "number"
				? displayValue.toString()
				: JSON.stringify(displayValue)}
		</span>
	);
}
