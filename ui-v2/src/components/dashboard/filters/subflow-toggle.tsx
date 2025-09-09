import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export type SubflowToggleProps = {
	value?: boolean;
	onChange: (value: boolean) => void;
	disabled?: boolean;
	className?: string;
};

export function SubflowToggle({
	value = false,
	onChange,
	disabled = false,
	className,
}: SubflowToggleProps) {
	return (
		<div className={cn("flex items-center space-x-2", className)}>
			<Checkbox
				id="hide-subflows"
				checked={value}
				onCheckedChange={(checked) => onChange(checked === true)}
				disabled={disabled}
			/>
			<Label
				htmlFor="hide-subflows"
				className="text-sm font-normal cursor-pointer"
			>
				Hide subflows
			</Label>
		</div>
	);
}
