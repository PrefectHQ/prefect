import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/lib/utils";

const calloutVariants = cva(
	"relative w-full rounded-lg border px-4 py-3 text-sm [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground [&>svg~*]:pl-7",
	{
		variants: {
			variant: {
				default: "bg-background text-foreground",
				info: "bg-blue-50 border-blue-200 text-blue-800",
				destructive:
					"border-destructive/50 text-destructive dark:border-destructive [&>svg]:text-destructive",
			},
		},
		defaultVariants: {
			variant: "default",
		},
	},
);

function Callout({
	className,
	variant,
	...props
}: React.HTMLAttributes<HTMLDivElement> &
	VariantProps<typeof calloutVariants>) {
	return (
		<div
			role="alert"
			className={cn(calloutVariants({ variant }), className)}
			{...props}
		/>
	);
}

function CalloutTitle({
	className,
	...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
	return (
		<h5
			className={cn("mb-1 font-medium leading-none tracking-tight", className)}
			{...props}
		/>
	);
}

function CalloutDescription({
	className,
	...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
	return (
		<div
			className={cn("text-sm [&_p]:leading-relaxed", className)}
			{...props}
		/>
	);
}

export { Callout, CalloutTitle, CalloutDescription };
