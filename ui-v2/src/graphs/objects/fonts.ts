import FontFaceObserver from "fontfaceobserver";
import {
	BitmapFont,
	BitmapText,
	type TextStyleOptions,
} from "pixi.js";
import { DEFAULT_TEXT_RESOLUTION } from "@/graphs/consts";
import { emitter, waitForEvent } from "@/graphs/objects/events";
import { waitForStyles } from "@/graphs/objects/styles";

export type FontFactory = (text: string) => BitmapText;

type BitmapFontStyle = {
	fontFamily: string;
	fontSize: number;
	lineHeight: number;
	fill: number;
};

let font: FontFactory | null = null;

const fontStyles = {
	fontFamily: "Inter Variable",
	fontSize: 16,
	lineHeight: 20,
	fill: 0xffffff,
} as const satisfies Readonly<BitmapFontStyle>;

const fallbackFontFamily = "sans-serif";

export async function startFonts(): Promise<void> {
	const { font: customFont } = await waitForStyles();

	const styles = {
		...fontStyles,
		fontFamily: customFont.fontFamily,
	};

	await loadFont(styles, customFont.type);

	font = fontFactory(styles);

	emitter.emit("fontLoaded", font);
}

async function loadFont(
	fontStyle: BitmapFontStyle,
	type: "BitmapFont" | "WebFont",
): Promise<void> {
	const { fontFamily: name, ...style } = fontStyle;

	try {
		if (type === "WebFont") {
			const observer = new FontFaceObserver(name);
			await observer.load();
		} else {
			BitmapFont.install({
				name,
				style: {
					fontFamily: fallbackFontFamily,
					...style,
				},
				resolution: DEFAULT_TEXT_RESOLUTION,
			});
			return;
		}
	} catch (error) {
		console.error(error);
		console.warn(
			`fonts: font ${name} failed to load, falling back to ${fallbackFontFamily}`,
		);

		BitmapFont.install({
			name,
			style: {
				fontFamily: fallbackFontFamily,
				...style,
			},
			resolution: DEFAULT_TEXT_RESOLUTION,
		});

		return;
	}

	BitmapFont.install({
		name,
		style: fontStyle,
		resolution: DEFAULT_TEXT_RESOLUTION,
	});
}

export function stopFonts(): void {
	font = null;
}

export async function waitForFonts(): Promise<FontFactory> {
	if (font) {
		return font;
	}

	return await waitForEvent("fontLoaded");
}

function fontFactory(style: BitmapFontStyle): FontFactory {
	const { fontFamily, ...fontStyle } = style;

	const textStyle: Partial<TextStyleOptions> = {
		fontFamily,
		...fontStyle,
	};

	return (text: string) => {
		return new BitmapText({ text, style: textStyle });
	};
}
