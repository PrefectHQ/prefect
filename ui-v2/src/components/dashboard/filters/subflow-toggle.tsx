import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export type SubflowToggleProps = {
	value?: boolean;
	onChange?: (value: boolean) => void;
	label?: string;
};

export const SubflowToggle = ({
	value = false,
	onChange,
	label = "Hide subflows",
}: SubflowToggleProps) => {
	return (
		<div className="flex items-center space-x-2">
			<Switch
				id="hide-subflows"
				checked={value}
				onCheckedChange={onChange}
				aria-label={label}
			/>
			<Label
				htmlFor="hide-subflows"
				className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
			>
				{label}
			</Label>
		</div>
	);
};
