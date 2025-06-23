import { create } from "storybook/theming";
import LogoDark from "./logos/logo-dark.svg";
import LogoLight from "./logos/logo-light.svg";

const BASE_THEME = {
	brandTitle: "Prefect",
	brandUrl: "https://prefect.io",
	brandTarget: "_self",
};

export const prefectLightTheme = create({
	...BASE_THEME,
	base: "light",
	brandImage: LogoLight,
});

export const prefectDarkTheme = create({
	...BASE_THEME,
	base: "dark",
	brandImage: LogoDark,
});
