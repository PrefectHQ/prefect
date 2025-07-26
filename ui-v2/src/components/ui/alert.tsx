import type * as React from "react";

import { cn } from "@/lib/utils";

interface AlertProps extends React.ComponentProps<"div"> {
	variant?: "default" | "destructive";
}

function Alert({ className, variant = "default", ...props }: AlertProps) {
	return (
		<div
			role="alert"
			className={cn(
				"relative w-full rounded-lg border p-4",
				{
					"border-border bg-background text-foreground": variant === "default",
					"border-red-500/50 bg-red-50 text-red-900 dark:border-red-500 dark:bg-red-950 dark:text-red-50":
						variant === "destructive",
				},
				className,
			)}
			{...props}
		/>
	);
}

function AlertTitle({ className, ...props }: React.ComponentProps<"h5">) {
	return (
		<h5
			className={cn("mb-1 font-medium leading-none tracking-tight", className)}
			{...props}
		/>
	);
}

function AlertDescription({
	className,
	...props
}: React.ComponentProps<"div">) {
	return (
		<div
			className={cn("text-sm [&_p]:leading-relaxed", className)}
			{...props}
		/>
	);
}

export { Alert, AlertTitle, AlertDescription };
