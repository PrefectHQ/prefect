import * as React from "react";

import { cn } from "@/lib/utils";

type InputProps = React.ComponentProps<"input"> & {
	className?: string;
	type?: React.HTMLInputTypeAttribute | undefined;
};

const Input = React.forwardRef<HTMLInputElement, InputProps>(
	({ className, type, ...props }, ref) => {
		return (
			<input
				type={type}
				className={cn(
					"flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
					className,
				)}
				ref={ref}
				{...props}
			/>
		);
	},
);
Input.displayName = "Input";

type IconInputProps = InputProps & {
	Icon: React.ElementType;
};

const IconInput = React.forwardRef<HTMLInputElement, IconInputProps>(
	({ className, Icon, ...props }, ref) => {
		return (
			<div className="relative w-full">
				<Icon className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground h-4 w-4" />
				<Input className={cn("pl-8", className)} ref={ref} {...props} />
			</div>
		);
	},
);
IconInput.displayName = "IconInput";

export { Input, type InputProps, IconInput };
