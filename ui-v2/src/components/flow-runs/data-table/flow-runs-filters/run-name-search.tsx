import { Icon } from "@/components/ui/icons";
import { Input, type InputProps } from "@/components/ui/input";

export const RunNameSearch = (props: InputProps) => {
	return (
		<div className="relative">
			<Input
				aria-label="search by run name"
				placeholder="Search by run name"
				className="pl-10"
				{...props}
			/>
			<Icon
				id="Search"
				className="absolute left-3 top-2.5 text-muted-foreground"
				size={18}
			/>
		</div>
	);
};
