import { ChevronDownIcon, ChevronRightIcon } from "@radix-ui/react-icons";
import { useState } from "react";

import { Button } from "@/components/ui/button";

import type { PropertyRendererProps } from "../types";

export function ArrayProperty({
	value,
	property,
	path,
}: PropertyRendererProps) {
	const [isExpanded, setIsExpanded] = useState(false);

	const displayValue = value ?? property.default ?? [];
	const isArray = Array.isArray(displayValue);

	if (!isArray) {
		return (
			<span className="font-mono text-sm text-muted-foreground">
				{JSON.stringify(displayValue)}
			</span>
		);
	}

	const array = displayValue as unknown[];

	if (array.length === 0) {
		return <span className="font-mono text-sm text-muted-foreground">[]</span>;
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
				[...] ({array.length} items)
			</Button>

			{isExpanded && (
				<div className="ml-4 space-y-1 border-l border-border pl-3">
					{array.map((item, index) => {
						const itemKey =
							typeof item === "object" && item !== null
								? `${path}[${index}]-${JSON.stringify(item).slice(0, 50)}`
								: `${path}[${index}]-${String(item)}`;
						return (
							<div key={itemKey} className="space-y-1">
								<div className="text-xs font-medium text-muted-foreground">
									[{index}]:
								</div>
								<div className="font-mono text-xs">
									{typeof item === "object" && item !== null
										? JSON.stringify(item, null, 2)
										: String(item)}
								</div>
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}
