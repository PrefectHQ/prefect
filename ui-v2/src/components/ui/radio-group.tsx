import * as React from "react";
import { cn } from "@/lib/utils";

interface RadioGroupProps {
	value?: string;
	onValueChange?: (value: string) => void;
	className?: string;
	children: React.ReactNode;
}

interface RadioGroupItemProps {
	value: string;
	className?: string;
	children: React.ReactNode;
	disabled?: boolean;
}

const RadioGroupContext = React.createContext<{
	value?: string;
	onValueChange?: (value: string) => void;
}>({});

function RadioGroup({
	value,
	onValueChange,
	className,
	children,
}: RadioGroupProps) {
	return (
		<RadioGroupContext.Provider value={{ value, onValueChange }}>
			<div className={cn("space-y-2", className)} role="radiogroup">
				{children}
			</div>
		</RadioGroupContext.Provider>
	);
}

function RadioGroupItem({
	value,
	className,
	children,
	disabled,
}: RadioGroupItemProps) {
	const context = React.useContext(RadioGroupContext);
	const isSelected = context.value === value;

	const handleClick = () => {
		if (!disabled && context.onValueChange) {
			context.onValueChange(value);
		}
	};

	return (
		<label
			className={cn(
				"cursor-pointer rounded-lg border p-4 transition-colors block",
				isSelected
					? "border-primary bg-primary/5"
					: "border-border hover:border-primary/50",
				disabled && "cursor-not-allowed opacity-50",
				className,
			)}
		>
			<div className="flex items-center space-x-2">
				<input
					type="radio"
					value={value}
					checked={isSelected}
					onChange={handleClick}
					disabled={disabled}
					className="sr-only"
				/>
				<div
					className={cn(
						"h-4 w-4 rounded-full border-2 transition-colors",
						isSelected
							? "border-primary bg-primary"
							: "border-muted-foreground",
					)}
				>
					{isSelected && (
						<div className="h-full w-full rounded-full bg-white scale-50" />
					)}
				</div>
				<div className="flex-1">{children}</div>
			</div>
		</label>
	);
}

export { RadioGroup, RadioGroupItem };
