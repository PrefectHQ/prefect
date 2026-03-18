import { Container } from "pixi.js";
import { DEFAULT_GUIDES_COUNT, DEFAULT_GUIDES_MIN_GAP } from "@/graphs/consts";
import { type GuideFactory, guideFactory } from "@/graphs/factories/guide";
import type { FormatDate } from "@/graphs/models/guides";
import { NonTemporalLayoutError } from "@/graphs/models/nonTemporalLayoutError";
import { waitForViewport } from "@/graphs/objects";
import { emitter } from "@/graphs/objects/events";
import { waitForScale } from "@/graphs/objects/scale";
import { waitForSettings } from "@/graphs/objects/settings";
import { repeat } from "@/graphs/utilities/repeat";
import {
	formatDateFns,
	labelFormats,
	type TimeIncrement,
	timeIncrements,
} from "@/graphs/utilities/timeIncrements";

const visibleGuideBoundsMargin = 300;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function guidesFactory() {
	const viewport = await waitForViewport();
	const settings = await waitForSettings();

	const element = new Container();
	const guides = new Map<number, GuideFactory>();

	let scale = await waitForScale();
	emitter.on("scaleUpdated", (updated) => (scale = updated));

	await createGuides();

	function render(): void {
		element.visible = !settings.disableGuides;

		if (settings.disableGuides) {
			return;
		}

		try {
			const { anchor, increment, labelFormat } = getIncrement();
			const times = getGuideTimes(anchor, increment);

			renderGuides(times, labelFormat);
		} catch (error) {
			if (error instanceof NonTemporalLayoutError) {
				// do nothing. we expect this to happen sometimes
				return;
			}

			console.error(error);
		}
	}

	async function createGuides(): Promise<void> {
		const promises: Promise<GuideFactory>[] = [];

		repeat(DEFAULT_GUIDES_COUNT, async (index) => {
			const promise = guideFactory();

			promises.push(promise);

			const guide = await promise;

			element.addChild(guide.element);
			guides.set(index, guide);
		});

		await Promise.all(promises);
	}

	// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
	function getIncrement() {
		const left = viewport.left - visibleGuideBoundsMargin;
		const start = scale.invert(left);
		const gapDate = scale.invert(
			left + DEFAULT_GUIDES_MIN_GAP / viewport.scale.x,
		);

		if (!(start instanceof Date) || !(gapDate instanceof Date)) {
			throw new NonTemporalLayoutError();
		}

		const gap = gapDate.getTime() - start.getTime();
		const { increment, getAnchor, labelFormat } = getTimeIncrement(gap);
		const anchor = getAnchor(start);

		return {
			anchor,
			increment,
			labelFormat: getLabelFormat(labelFormat),
		};
	}

	function getTimeIncrement(gap: number): Required<TimeIncrement> {
		const selected =
			timeIncrements.find((timeSlot) => timeSlot.ceiling > gap) ??
			timeIncrements[0];

		if (!selected.getAnchor) {
			selected.getAnchor = (start: Date) =>
				Math.floor(start.getTime() / selected.increment) * selected.increment;
		}

		return selected as Required<TimeIncrement>;
	}

	function getLabelFormat(labelFormat: string): FormatDate {
		switch (labelFormat) {
			case labelFormats.minutes:
				return formatDateFns.timeByMinutesWithDates;
			case labelFormats.date:
				return formatDateFns.date;
			default:
				return formatDateFns.timeBySeconds;
		}
	}

	function renderGuides(times: number[], labelFormat: FormatDate): void {
		const guidesStore = new Map(guides.entries());
		const unused = Array.from(guidesStore.keys()).filter(
			(time) => !times.includes(time),
		);

		guides.clear();

		for (const time of times) {
			if (guidesStore.has(time)) {
				const guide = guidesStore.get(time)!;

				guides.set(time, guide);
				guide.render(new Date(time), labelFormat);

				continue;
			}

			const guide = guidesStore.get(unused.pop() ?? -1);

			if (guide === undefined) {
				console.warn("Guides: No unused guides available to render.");
				continue;
			}

			guide.render(new Date(time), labelFormat);
			guides.set(time, guide);
		}
	}

	function getGuideTimes(anchor: number, increment: number): number[] {
		return repeat(DEFAULT_GUIDES_COUNT, (index) => {
			return anchor + increment * index;
		});
	}

	return {
		element,
		render,
	};
}
