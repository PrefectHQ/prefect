import { Container } from "pixi.js";
import { rectangleFactory } from "@/graphs/factories/rectangle";
import type { FormatDate } from "@/graphs/models/guides";
import { waitForViewport } from "@/graphs/objects";
import { waitForApplication } from "@/graphs/objects/application";
import { emitter } from "@/graphs/objects/events";
import { waitForFonts } from "@/graphs/objects/fonts";
import { waitForScale } from "@/graphs/objects/scale";
import { waitForSettings } from "@/graphs/objects/settings";
import { waitForStyles } from "@/graphs/objects/styles";

export type GuideFactory = Awaited<ReturnType<typeof guideFactory>>;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function guideFactory() {
	const application = await waitForApplication();
	const viewport = await waitForViewport();
	const settings = await waitForSettings();
	const styles = await waitForStyles();
	const font = await waitForFonts();
	const element = new Container();

	const rectangle = await rectangleFactory();
	element.addChild(rectangle);

	const label = font("");
	element.addChild(label);

	let scale = await waitForScale();
	let currentDate: Date | undefined;
	let currentLabelFormatter: FormatDate;

	emitter.on("scaleUpdated", (updated) => {
		scale = updated;
		updatePosition();
	});
	emitter.on("viewportMoved", () => {
		if (settings.disableGuides) {
			return;
		}

		updatePosition();

		if (element.height !== application.screen.height) {
			renderLine();
		}
	});

	function render(date: Date, labelFormatter: FormatDate): void {
		currentDate = date;
		currentLabelFormatter = labelFormatter;

		renderLine();
		renderLabel(date);
	}

	function renderLine(): void {
		rectangle.width = styles.guideLineWidth;
		rectangle.height = application.screen.height;
		rectangle.tint = styles.guideLineColor;
	}

	function renderLabel(date: Date): void {
		label.text = currentLabelFormatter(date);
		label.style.fontSize = styles.guideTextSize;
		label.tint = styles.guideTextColor;
		label.position.set(styles.guideTextLeftPadding, styles.guideTextTopPadding);
	}

	function updatePosition(): void {
		if (currentDate !== undefined) {
			element.position.x =
				scale(currentDate) * viewport.scale._x + viewport.worldTransform.tx;
		}
	}

	return {
		element,
		render,
	};
}
