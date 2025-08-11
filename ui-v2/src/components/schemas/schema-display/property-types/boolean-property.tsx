import type { PropertyRendererProps } from "../types";

export function BooleanProperty({ value, property }: PropertyRendererProps) {
	const displayValue = value ?? property.default ?? false;

	return (
		<span className="font-mono text-sm">
			{typeof displayValue === "boolean"
				? displayValue.toString()
				: JSON.stringify(displayValue)}
		</span>
	);
}
