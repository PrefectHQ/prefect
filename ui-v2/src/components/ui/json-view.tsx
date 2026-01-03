import type * as React from "react";
import { cn } from "@/utils";
import { LazyJsonInput as JsonInput } from "./json-input-lazy";

type JsonViewProps = Omit<
	React.ComponentProps<typeof JsonInput>,
	"onChange" | "onBlur" | "disabled"
> & {
	value?: string;
	className?: string;
	hideLineNumbers?: boolean;
	copy?: boolean;
};

export function JsonView({
	value,
	className,
	hideLineNumbers = true,
	copy = true,
	...props
}: JsonViewProps) {
	return (
		<JsonInput
			value={value}
			disabled={true}
			hideLineNumbers={hideLineNumbers}
			copy={copy}
			className={cn("bg-muted/50", className)}
			{...props}
		/>
	);
}
