import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphFullscreenButton } from "./flow-run-graph-fullscreen-button";

const pressKey = (key: string) => fireEvent.keyDown(document, { key });

describe("FlowRunGraphFullscreenButton", () => {
	it("does not enter fullscreen when Escape is pressed", () => {
		const onFullscreenChange = vi.fn();
		render(
			<FlowRunGraphFullscreenButton
				fullscreen={false}
				onFullscreenChange={onFullscreenChange}
			/>,
		);

		pressKey("Escape");

		expect(onFullscreenChange).not.toHaveBeenCalled();
	});

	it("leaves fullscreen when Escape is pressed", () => {
		const onFullscreenChange = vi.fn();
		render(
			<FlowRunGraphFullscreenButton
				fullscreen
				onFullscreenChange={onFullscreenChange}
			/>,
		);

		pressKey("Escape");

		expect(onFullscreenChange).toHaveBeenCalledWith(false);
	});

	it("toggles fullscreen with f", () => {
		const onFullscreenChange = vi.fn();
		render(
			<FlowRunGraphFullscreenButton
				fullscreen={false}
				onFullscreenChange={onFullscreenChange}
			/>,
		);

		pressKey("f");

		expect(onFullscreenChange).toHaveBeenCalledWith(true);
	});
});
