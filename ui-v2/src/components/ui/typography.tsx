import { cn } from "@/lib/utils";
import { forwardRef } from "react";

type Variant = "h1" | "h2" | "h3" | "h4" | "bodyLarge" | "body" | "bodySmall";

type Props = {
	className?: string;
	variant?: Variant;
	children: React.ReactNode;
};

export const Typography = forwardRef<HTMLDivElement, Props>(
	({ variant = "body", className, children }, ref) => {
		switch (variant) {
			case "h1":
				return (
					<h1
						ref={ref}
						className={cn("text-4xl font-extrabold tracking-tight", className)}
					>
						{children}
					</h1>
				);
			case "h2":
				return (
					<h2
						ref={ref}
						className={cn("text-3xl  font-semibold tracking-tight", className)}
					>
						{children}
					</h2>
				);
			case "h3":
				return (
					<h3
						ref={ref}
						className={cn("text-2xl font-semibold tracking-tight", className)}
					>
						{children}
					</h3>
				);
			case "h4":
				return (
					<h4
						ref={ref}
						className={cn("text-xl font-semibold tracking-tight", className)}
					>
						{children}
					</h4>
				);

			case "bodyLarge":
				return (
					<h4 ref={ref} className={cn("text-lg", className)}>
						{children}
					</h4>
				);

			case "bodySmall":
				return (
					<p ref={ref} className={cn("text-sm", className)}>
						{children}
					</p>
				);

			case "body":
			default:
				return (
					<p ref={ref} className={cn("text-base", className)}>
						{children}
					</p>
				);
		}
	},
);
Typography.displayName = "Typography";
