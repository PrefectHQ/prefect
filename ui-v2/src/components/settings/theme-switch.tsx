import { Icon } from "@/components/ui/icons";
import { Switch } from "@/components/ui/switch";

// TODO: Switch for dark mode provider

export const ThemeSwitch = () => {
	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="theme-switch">Theme</label>
			<div className="flex gap-2 items-center">
				<Icon id="Sun" className="h-4 w-4" />
				<Switch />
				<Icon id="Moon" className="h-7 w-4" />
			</div>
		</div>
	);
};
