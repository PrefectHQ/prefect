import React from "react";
import { vi } from "vitest";

//  Mock out JsonInput because the underlying CodeMirror editor
// relies on browser APIs that are not available in JSDOM.
// TODO: Ensure input into JsonInput is covered by Playwright tests.
export const MockJsonInput = React.forwardRef<
	HTMLTextAreaElement,
	{
		value: string;
		onChange?: (value: string) => void;
	}
>((props, ref) => {
	return (
		<textarea
			ref={ref}
			value={props.value}
			onChange={(e) => {
				props.onChange?.(e.target.value);
			}}
			data-testid="mock-json-input"
		/>
	);
});

MockJsonInput.displayName = "MockJsonInput";

vi.mock("@/components/ui/json-input", () => ({
	JsonInput: MockJsonInput,
}));
