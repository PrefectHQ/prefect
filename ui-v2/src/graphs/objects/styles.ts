import type {
	RequiredGraphConfig,
	RunGraphStyles,
	RunGraphTheme,
} from "@/graphs/models/RunGraph";
import { waitForConfig } from "@/graphs/objects/config";
import { emitter, waitForEvent } from "@/graphs/objects/events";

function getCssVar(name: string, fallback: string): string {
	if (typeof document === "undefined") return fallback;
	const value = getComputedStyle(document.documentElement)
		.getPropertyValue(name)
		.trim();
	return value || fallback;
}

const defaults: (theme: RunGraphTheme) => Required<RunGraphStyles> = (
	theme,
) => ({
	font: {
		fontFamily:
			"ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'",
		type: "BitmapFont",
	},
	rowGap: 24,
	columnGap: 32,
	textDefault: getCssVar("--foreground", theme === "dark" ? "#ffffff" : "#161618"),
	textInverse: getCssVar("--background", theme === "dark" ? "#161618" : "#ffffff"),
	selectedBorderColor: getCssVar("--primary", theme === "dark" ? "#3fa2c3" : "#297f9c"),
	selectedBorderWidth: 2,
	selectedBorderOffset: 4,
	selectedBorderRadius: 9,
	nodesPadding: 16,
	nodeHeight: 32,
	nodePadding: 4,
	nodeRadius: 6,
	nodeBorderRadius: 9,
	nodeToggleSize: 28,
	nodeToggleBgColor: getCssVar("--muted", "#35363C"),
	nodeToggleBorderRadius: 6,
	nodeToggleBorderColor: getCssVar("--border", theme === "dark" ? "#4d4f56" : "#bbbec9"),
	nodeUnselectedAlpha: 0.2,
	artifactsGap: 4,
	artifactsNodeOverlap: 4,
	artifactPaddingLeft: 2,
	artifactPaddingRight: 4,
	artifactPaddingY: 2,
	artifactTextColor: getCssVar("--primary-foreground", "#ffffff"),
	artifactBgColor: getCssVar("--secondary", "#35363b"),
	artifactBorderRadius: 4,
	artifactContentGap: 4,
	artifactIconSize: 16,
	artifactIconColor: getCssVar("--primary-foreground", "#ffffff"),
	flowStateBarHeight: 8,
	flowStateSelectedBarHeight: 10,
	flowStateAreaAlpha: 0.1,
	eventTargetSize: 30,
	eventBottomMargin: 4,
	eventSelectedBorderInset: 8,
	eventRadiusDefault: 4,
	eventColor: getCssVar("--event", "#A564F9"),
	eventClusterRadiusDefault: 6,
	eventClusterColor: getCssVar("--event", "#A564F9"),
	edgeColor: getCssVar("--muted-foreground", theme === "dark" ? "#adadad" : "#737682"),
	guideLineWidth: 1,
	guideLineColor: getCssVar("--border", theme === "dark" ? "#4d4f56" : "#bbbec9"),
	guideTextTopPadding: 8,
	guideTextLeftPadding: 8,
	guideTextSize: 12,
	guideTextColor: getCssVar("--muted-foreground", theme === "dark" ? "#adadad" : "#737682"),
	playheadWidth: 2,
	playheadColor: getCssVar("--primary", "#6272FF"),
	node: () => ({
		background: getCssVar("--card", "#ffffff"),
	}),
	state: () => ({
		background: getCssVar("--card", "#ffffff"),
	}),
});

let styles: Required<RunGraphStyles> | null = null;

export async function startStyles(): Promise<void> {
	const config = await waitForConfig();

	styles = getStyles(config);

	emitter.emit("stylesCreated", styles);

	emitter.on("configUpdated", (config) => {
		styles = getStyles(config);
		emitter.emit("stylesUpdated", styles);
	});
}

export function stopStyles(): void {
	styles = null;
}

export async function waitForStyles(): Promise<Required<RunGraphStyles>> {
	if (styles) {
		return styles;
	}

	return await waitForEvent("stylesCreated");
}

function getStyles(config: RequiredGraphConfig): Required<RunGraphStyles> {
	return {
		...defaults(config.theme),
		...config.styles?.(config.theme),
	};
}
