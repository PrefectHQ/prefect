import { useMemo } from "react";
import { PythonInput } from "@/components/ui/python-input";

type PythonBlockSnippetProps = {
	codeExample: string;
	name: string | undefined | null;
};
export function PythonBlockSnippet({
	codeExample,
	name,
}: PythonBlockSnippetProps) {
	const snippet = useMemo(() => {
		const [, genericSnippet = ""] =
			codeExample.match(/```python([\S\s]*?)```/) ?? [];
		const customSnippet = genericSnippet.replace(
			"BLOCK_NAME",
			name ?? "block-name",
		);
		return customSnippet.trim();
	}, [codeExample, name]);

	return (
		<div className="flex flex-col gap-4">
			<PythonInput
				className="p-2"
				value={snippet}
				disabled
				copy
				hideLineNumbers
			/>
		</div>
	);
}
