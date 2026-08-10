import { useEffect } from "react";

export type SchemaFormInputNullProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
};

export function SchemaFormInputNull({
	value,
	onValueChange,
}: SchemaFormInputNullProps) {
	useEffect(() => {
		if (value !== null) {
			onValueChange(null);
		}
	}, [value, onValueChange]);

	return (
		<p className="text-subdued text-sm">Property is type &quot;None&quot;</p>
	);
}
