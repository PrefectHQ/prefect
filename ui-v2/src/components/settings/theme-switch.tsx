import { useTheme } from "next-themes";
import { Icon } from "@/components/ui/icons";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export const ThemeSwitch = () => {
	const { theme, setTheme } = useTheme();

	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="color-mode-select">Theme</label>
			<div className="space-y-3">
				<RadioGroup
					value={theme}
					onValueChange={setTheme}
					className="grid grid-cols-3 gap-4"
				>
					<div>
						<RadioGroupItem value="light" id="light" className="peer sr-only" />
						<Label
							htmlFor="light"
							className="flex items-center space-x-2 rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary cursor-pointer"
						>
							<Icon id="Sun" className="h-6 w-6" />
							<span>Light</span>
						</Label>
					</div>
					<div>
						<RadioGroupItem value="dark" id="dark" className="peer sr-only" />
						<Label
							htmlFor="dark"
							className="flex items-center space-x-2 rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary cursor-pointer"
						>
							<Icon id="Moon" className="h-6 w-6" />
							<span>Dark</span>
						</Label>
					</div>
					<div>
						<RadioGroupItem
							value="system"
							id="system"
							className="peer sr-only"
						/>
						<Label
							htmlFor="system"
							className="flex items-center space-x-2 rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary cursor-pointer"
						>
							<Icon id="Monitor" className="h-6 w-6" />
							<span>System</span>
						</Label>
					</div>
				</RadioGroup>
			</div>
		</div>
	);
};
