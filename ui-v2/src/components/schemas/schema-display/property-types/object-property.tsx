import { ChevronDownIcon, ChevronRightIcon } from "@radix-ui/react-icons";
import { useState } from "react";

import { Button } from "@/components/ui/button";

import type { PropertyRendererProps } from "../types";

export function ObjectProperty({
	value,
	property,
	path,
}: PropertyRendererProps) {
	const [isExpanded, setIsExpanded] = useState(false);

	const displayValue = value ?? property.default ?? {};
	const isObject = typeof displayValue === "object" && displayValue !== null;

	if (!isObject) {
		return (
			<span className="font-mono text-sm text-muted-foreground">
				{JSON.stringify(displayValue)}
			</span>
		);
	}

	const entries = Object.entries(displayValue as Record<string, unknown>);

	if (entries.length === 0) {
		return (
			<span className="font-mono text-sm text-muted-foreground">
				{"{"}
				{"}"}
			</span>
		);
	}

	return (
		<div className="space-y-1">
			<Button
				variant="ghost"
				size="sm"
				className="h-auto p-0 font-mono text-sm"
				onClick={() => setIsExpanded(!isExpanded)}
			>
				{isExpanded ? (
					<ChevronDownIcon className="mr-1 h-3 w-3" />
				) : (
					<ChevronRightIcon className="mr-1 h-3 w-3" />
				)}
				{"{"}...{"}"} ({entries.length} properties)
			</Button>

			{isExpanded && (
				<div className="ml-4 space-y-1 border-l border-border pl-3">
					{entries.map(([key, val]) => (
						<div key={`${path}.${key}`} className="space-y-1">
							<div className="text-xs font-medium text-muted-foreground">
								{key}:
							</div>
							<div className="font-mono text-xs">
								{typeof val === "object" && val !== null
									? JSON.stringify(val, null, 2)
									: String(val)}
							</div>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
