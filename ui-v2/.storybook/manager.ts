import { addons } from "storybook/manager-api";

import favicon from "../public/ico/favicon-16x16-dark.png";
import { prefectLightTheme } from "./prefect-theme";

addons.setConfig({
	theme: prefectLightTheme,
});

// custom favicon
const link = document.createElement("link");
link.setAttribute("rel", "shortcut icon");
link.setAttribute("href", favicon);
document.head.appendChild(link);
