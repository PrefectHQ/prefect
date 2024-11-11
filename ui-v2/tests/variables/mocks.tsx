import { vi } from "vitest";
import React from "react";

export const MockCodeMirror = React.forwardRef<
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
			data-testid="mock-codemirror"
		/>
	);
});

MockCodeMirror.displayName = "MockCodemirror";

vi.mock("@uiw/react-codemirror", () => ({
	default: MockCodeMirror,
	json: () => ({}),
	EditorView: {
		theme: () => ({}),
	},
}));
