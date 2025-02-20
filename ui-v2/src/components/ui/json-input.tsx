import React, { useRef, useEffect } from "react";

import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { json } from "@codemirror/lang-json";
import {
	type BasicSetupOptions,
	EditorView,
	useCodeMirror,
} from "@uiw/react-codemirror";
import { Button } from "./button";
import { Icon } from "./icons";

const extensions = [json(), EditorView.lineWrapping];

type JsonInputProps = React.ComponentProps<"div"> & {
	value?: string;
	onChange?: (value: string) => void;
	onBlur?: () => void;
	disabled?: boolean;
	className?: string;
	hideLineNumbers?: boolean;
	copy?: boolean;
};

export const JsonInput = React.forwardRef<HTMLDivElement, JsonInputProps>(
	(
		{
			className,
			value,
			onChange,
			copy = false,
			onBlur,
			disabled,
			hideLineNumbers = false,
			...props
		},
		forwardedRef,
	) => {
		const { toast } = useToast();
		const editor = useRef<HTMLDivElement | null>(null);
		// Setting `basicSetup` messes up the tab order. We only change the basic setup
		// if the input is disabled, so we leave it undefined to maintain the tab order.
		let basicSetup: BasicSetupOptions | undefined;
		if (disabled) {
			basicSetup = {
				lineNumbers: !hideLineNumbers,
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

		const handleCopy = (_value: string) => {
			toast({ title: "Copied to clipboard" });
			void navigator.clipboard.writeText(_value);
		};

		return (
			<div
				className={cn(
					"rounded-md border shadow-sm overflow-hidden focus-within:outline-none focus-within:ring-1 focus-within:ring-ring relative",
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
			>
				{copy && value && (
					<Button
						onClick={() => handleCopy(value)}
						variant="ghost"
						size="icon"
						className="absolute top-0 right-0 z-10"
						aria-label="copy"
					>
						<Icon id="Copy" className="h-2 w-2" />
					</Button>
				)}
			</div>
		);
	},
);

JsonInput.displayName = "JsonInput";
