import { markdown } from "@codemirror/lang-markdown";
import {
	type BasicSetupOptions,
	EditorView,
	useCodeMirror,
} from "@uiw/react-codemirror";
import React, { useEffect, useRef } from "react";
import { toast } from "sonner";
import { cn } from "@/utils";
import { Button } from "./button";
import { Icon } from "./icons";

const extensions = [markdown(), EditorView.lineWrapping];

type MarkdownInputProps = React.ComponentProps<"div"> & {
	value?: string;
	onChange?: (value: string) => void;
	onBlur?: () => void;
	disabled?: boolean;
	className?: string;
	hideLineNumbers?: boolean;
	copy?: boolean;
};

export const MarkdownInput = React.forwardRef<
	HTMLDivElement,
	MarkdownInputProps
>(
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
			toast.success("Copied to clipboard");
			void navigator.clipboard.writeText(_value);
		};

		return (
			<div
				className={cn(
					"rounded-md border shadow-xs overflow-hidden focus-within:outline-hidden focus-within:ring-1 focus-within:ring-ring relative",
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
						<Icon id="Copy" className="size-2" />
					</Button>
				)}
			</div>
		);
	},
);

MarkdownInput.displayName = "MarkdownInput";
