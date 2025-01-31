import React, { useRef, useEffect } from "react";

import { cn } from "@/lib/utils";
import { json } from "@codemirror/lang-json";
import {
	type BasicSetupOptions,
	EditorView,
	useCodeMirror,
} from "@uiw/react-codemirror";

const extensions = [json(), EditorView.lineWrapping];

type JsonInputProps = React.ComponentProps<"div"> & {
	value?: string;
	onChange?: (value: string) => void;
	onBlur?: () => void;
	disabled?: boolean;
	className?: string;
};

export const JsonInput = React.forwardRef<HTMLDivElement, JsonInputProps>(
	(
		{ className, value, onChange, onBlur, disabled, ...props },
		forwardedRef,
	) => {
		const editor = useRef<HTMLDivElement | null>(null);
		// Setting `basicSetup` messes up the tab order. We only change the basic setup
		// if the input is disabled, so we leave it undefined to maintain the tab order.
		let basicSetup: BasicSetupOptions | undefined;
		if (disabled) {
			basicSetup = {
				highlightActiveLine: false,
				foldGutter: false,
				highlightActiveLineGutter: false,
			};
		}
		const { setContainer } = useCodeMirror({
			container: editor.current,
			extensions,
			value,
			onChange,
			onBlur,
			indentWithTab: false,
			editable: !disabled,
			basicSetup,
		});

		useEffect(() => {
			if (editor.current) {
				setContainer(editor.current);
			}
		}, [setContainer]);

		return (
			<div
				className={cn(
					"rounded-md border shadow-xs overflow-hidden focus-within:outline-hidden focus-within:ring-1 focus-within:ring-ring",
					className,
				)}
				ref={(node) => {
					editor.current = node;
					if (typeof forwardedRef === "function") {
						forwardedRef(node);
					} else if (forwardedRef) {
						forwardedRef.current = node;
					}
				}}
				{...props}
			/>
		);
	},
);

JsonInput.displayName = "JsonInput";
