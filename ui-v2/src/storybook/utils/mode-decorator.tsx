import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { StoryFn } from "@storybook/react";
import { useEffect, useState } from "react";

export const ModeDecorator = (Story: StoryFn) => {
	const [isDarkMode, setIsDarkMode] = useState(false);
	const toggleMode = () => {
		setIsDarkMode((curr) => !curr);
	};

	// sync external css  with state
	useEffect(() => {
		document.documentElement.classList.toggle("dark", isDarkMode);
	}, [isDarkMode]);

	return (
		<>
			<div className="absolute bottom-4 left-4 z-50">
				<div className="flex items-center space-x-2">
					<Switch id="theme-mode" checked={isDarkMode} onClick={toggleMode} />
					<Label htmlFor="theme-mode">
						{isDarkMode ? "Light Mode" : "Dark Mode (experimental)"}
					</Label>
				</div>
			</div>
			{/** @ts-expect-error Error typing from React 19 types upgrade. Will need to wait for this up be updated */}
			<Story />
		</>
	);
};
