import { Icon } from "@/components/ui/icons";
import { Switch } from "@/components/ui/switch";

import { useLocalStorage } from "@/hooks/use-local-storage";
import { useEffect } from "react";

const isOSDarkModePreferred = window.matchMedia(
	"(prefers-color-scheme: dark)",
).matches;

type ColorScheme = "light" | "dark";

export const ThemeSwitch = () => {
	const [colorScheme, setColorScheme] = useLocalStorage<ColorScheme>(
		"color-scheme",
		isOSDarkModePreferred ? "dark" : "light",
	);

	// Synchronizes document to dark mode theme
	useEffect(() => {
		if (colorScheme === "dark") {
			document.body.classList.add("dark");
		} else {
			document.body.classList.remove("dark");
		}
	}, [colorScheme]);

	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="theme-switch">Theme</label>
			<div className="flex gap-2 items-center">
				<Icon id="Sun" className="size-4" />
				<Switch
					checked={colorScheme === "dark"}
					onCheckedChange={(checked) =>
						setColorScheme(checked ? "dark" : "light")
					}
				/>
				<Icon id="Moon" className="size-4" />
			</div>
		</div>
	);
};
