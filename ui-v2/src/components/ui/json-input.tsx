import React, { useRef, useEffect } from "react";

import { json } from "@codemirror/lang-json";
import { cn } from "@/lib/utils";
import { useCodeMirror } from "@uiw/react-codemirror";

const extensions = [json()];

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
		const { setContainer } = useCodeMirror({
			container: editor.current,
			extensions,
			value,
			onChange,
			onBlur,
			indentWithTab: false,
			editable: !disabled,
		});

		useEffect(() => {
			if (editor.current) {
				setContainer(editor.current);
			}
		}, [setContainer]);

		return (
			<div
				className={cn(
					"rounded-md border shadow-sm overflow-hidden focus-within:outline-none focus-within:ring-1 focus-within:ring-ring",
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
