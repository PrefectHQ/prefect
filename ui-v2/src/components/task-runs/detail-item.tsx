import type React from "react";

export type DetailItemProps = {
	label: string;
	value: React.ReactNode;
	monospace?: boolean;
};

export const DetailItem = ({
	label,
	value,
	monospace = false,
}: DetailItemProps) => {
	if (value === null || value === undefined) return null;

	return (
		<div className="flex flex-col gap-1 mb-2">
			<span className="text-xs text-gray-500">{label}</span>
			<span className={monospace ? "font-mono text-sm" : "text-sm"}>
				{value}
			</span>
		</div>
	);
};
