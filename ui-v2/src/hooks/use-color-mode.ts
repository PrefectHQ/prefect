import { useCallback, useEffect } from "react";
import { useLocalStorage } from "./use-local-storage";

export const COLOR_MODES = [
	"default",
	"achromatopsia",
	"deuteranopia",
	"deuteranomaly",
	"protanopia",
	"protanomaly",
	"tritanomaly",
	"tritanopia",
	"high-contrast",
	"low-contrast",
] as const;

export type ColorMode = (typeof COLOR_MODES)[number];

const COLOR_MODE_STORAGE_KEY = "prefect-color-mode";

function getColorModeClass(mode: ColorMode): string {
	return `color-mode-${mode}`;
}

export function useColorMode() {
	const [colorMode, setColorModeStorage] = useLocalStorage<ColorMode>(
		COLOR_MODE_STORAGE_KEY,
		"default",
	);

	const applyColorMode = useCallback((mode: ColorMode) => {
		// Remove all color mode classes
		COLOR_MODES.forEach((m) => {
			document.body.classList.remove(getColorModeClass(m));
		});
		// Add new color mode class
		document.body.classList.add(getColorModeClass(mode));
	}, []);

	const setColorMode = useCallback(
		(mode: ColorMode) => {
			setColorModeStorage(mode);
			applyColorMode(mode);
		},
		[setColorModeStorage, applyColorMode],
	);

	// Apply color mode on mount and when it changes
	useEffect(() => {
		applyColorMode(colorMode);
	}, [colorMode, applyColorMode]);

	return { colorMode, setColorMode, colorModes: COLOR_MODES };
}
