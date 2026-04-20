import type { Meta, StoryObj } from "@storybook/react";
import type { JSX } from "react";

const meta: Meta = {
	title: "UI/ColorPalette",
	render: () => <ColorPalette />,
};

export default meta;

export const story: StoryObj = { name: "ColorPalette" };

const themeColors = [
	{ name: "background", variable: "--background" },
	{ name: "foreground", variable: "--foreground" },
	{ name: "card", variable: "--card" },
	{ name: "card-foreground", variable: "--card-foreground" },
	{ name: "popover", variable: "--popover" },
	{ name: "popover-foreground", variable: "--popover-foreground" },
	{ name: "primary", variable: "--primary" },
	{ name: "primary-foreground", variable: "--primary-foreground" },
	{ name: "secondary", variable: "--secondary" },
	{ name: "secondary-foreground", variable: "--secondary-foreground" },
	{ name: "muted", variable: "--muted" },
	{ name: "muted-foreground", variable: "--muted-foreground" },
	{ name: "accent", variable: "--accent" },
	{ name: "accent-foreground", variable: "--accent-foreground" },
	{ name: "destructive", variable: "--destructive" },
	{ name: "destructive-foreground", variable: "--destructive-foreground" },
	{ name: "border", variable: "--border" },
	{ name: "input", variable: "--input" },
	{ name: "ring", variable: "--ring" },
];

const sentimentColors = [
	{ name: "positive", variable: "--sentiment-positive" },
	{ name: "neutral", variable: "--sentiment-neutral" },
	{ name: "warning", variable: "--sentiment-warning" },
	{ name: "negative", variable: "--sentiment-negative" },
];

const chartColors = [
	{ name: "chart-1", variable: "--chart-1" },
	{ name: "chart-2", variable: "--chart-2" },
	{ name: "chart-3", variable: "--chart-3" },
	{ name: "chart-4", variable: "--chart-4" },
	{ name: "chart-5", variable: "--chart-5" },
];

const sidebarColors = [
	{ name: "sidebar-background", variable: "--sidebar-background" },
	{ name: "sidebar-foreground", variable: "--sidebar-foreground" },
	{ name: "sidebar-primary", variable: "--sidebar-primary" },
	{
		name: "sidebar-primary-foreground",
		variable: "--sidebar-primary-foreground",
	},
	{ name: "sidebar-accent", variable: "--sidebar-accent" },
	{
		name: "sidebar-accent-foreground",
		variable: "--sidebar-accent-foreground",
	},
	{ name: "sidebar-border", variable: "--sidebar-border" },
	{ name: "sidebar-ring", variable: "--sidebar-ring" },
];

const stateTypes = [
	{ name: "completed", label: "Completed (Green)" },
	{ name: "failed", label: "Failed (Red)" },
	{ name: "running", label: "Running (Blue)" },
	{ name: "pending", label: "Pending (Gray/Purple)" },
	{ name: "paused", label: "Paused (Gray/Purple)" },
	{ name: "scheduled", label: "Scheduled (Yellow)" },
	{ name: "cancelled", label: "Cancelled (Gray)" },
	{ name: "cancelling", label: "Cancelling (Blue-Gray)" },
	{ name: "crashed", label: "Crashed (Orange)" },
];

const shades = [
	"50",
	"100",
	"200",
	"300",
	"400",
	"500",
	"600",
	"700",
	"800",
	"900",
];

function ColorSwatch({
	variable,
	name,
}: {
	variable: string;
	name: string;
}): JSX.Element {
	return (
		<div className="flex items-center gap-3">
			<div
				className="w-12 h-12 rounded-md border border-border shadow-sm"
				style={{ backgroundColor: `var(${variable})` }}
			/>
			<div className="flex flex-col">
				<span className="text-sm font-medium">{name}</span>
				<span className="text-xs text-muted-foreground font-mono">
					{variable}
				</span>
			</div>
		</div>
	);
}

function ColorSection({
	title,
	colors,
}: {
	title: string;
	colors: { name: string; variable: string }[];
}): JSX.Element {
	return (
		<div className="mb-8">
			<h2 className="text-lg font-semibold mb-4 border-b pb-2">{title}</h2>
			<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
				{colors.map((color) => (
					<ColorSwatch
						key={color.variable}
						variable={color.variable}
						name={color.name}
					/>
				))}
			</div>
		</div>
	);
}

function StateColorPalette({
	stateName,
	label,
}: {
	stateName: string;
	label: string;
}): JSX.Element {
	return (
		<div className="mb-6">
			<h3 className="text-md font-medium mb-3">{label}</h3>
			<div className="flex gap-1">
				{shades.map((shade) => (
					<div key={shade} className="flex flex-col items-center">
						<div
							className="w-10 h-10 rounded-md border border-border/50"
							style={{ backgroundColor: `var(--state-${stateName}-${shade})` }}
						/>
						<span className="text-xs text-muted-foreground mt-1">{shade}</span>
					</div>
				))}
			</div>
		</div>
	);
}

function ColorPalette(): JSX.Element {
	return (
		<div className="p-6 bg-background text-foreground">
			<h1 className="text-2xl font-bold mb-6">Prefect Color Palette</h1>
			<p className="text-muted-foreground mb-8">
				This palette uses Prefect Blue (hue 228) as the primary color. All theme
				tokens are designed to match the V1 UI color scheme.
			</p>

			<ColorSection title="Core Theme Colors" colors={themeColors} />
			<ColorSection title="Sentiment Colors" colors={sentimentColors} />
			<ColorSection title="Chart Colors" colors={chartColors} />
			<ColorSection title="Sidebar Colors" colors={sidebarColors} />

			<div className="mb-8">
				<h2 className="text-lg font-semibold mb-4 border-b pb-2">
					State Colors
				</h2>
				<p className="text-muted-foreground mb-4">
					Each flow run state has a full color scale from 50 (lightest) to 900
					(darkest).
				</p>
				{stateTypes.map((state) => (
					<StateColorPalette
						key={state.name}
						stateName={state.name}
						label={state.label}
					/>
				))}
			</div>
		</div>
	);
}
