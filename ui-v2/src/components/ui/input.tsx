import useDebounce from "@/hooks/use-debounce";
import { cn } from "@/lib/utils";
import * as React from "react";
import { useEffect, useState } from "react";
import { ICONS } from "./icons";

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

type SearchInputProps = Omit<IconInputProps, "Icon"> & {
	debounceMs?: number;
};

const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
	({ className, debounceMs = 200, onChange, value, ...props }, ref) => {
		const [state, setState] = useState<{
			value: typeof value;
			event?: React.ChangeEvent<HTMLInputElement>;
		}>({ value });
		const debouncedValue = useDebounce(state.value, debounceMs);

		useEffect(() => {
			if (debouncedValue && state.event) {
				onChange?.(state.event);
			}
		}, [debouncedValue, onChange, state.event]);

		useEffect(() => {
			setState({ value });
		}, [value]);

		return (
			<IconInput
				Icon={ICONS.Search}
				className={className}
				ref={ref}
				value={state.value}
				onChange={(e) => setState({ value: e.target.value, event: e })}
				{...props}
			/>
		);
	},
);
SearchInput.displayName = "SearchInput";

export { Input, type InputProps, IconInput, SearchInput };
