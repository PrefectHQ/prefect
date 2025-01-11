import { vi } from "vitest";

export const mockPointerEvents = () => {
	// Need to mock PointerEvent for the selects to work
	class MockPointerEvent extends Event {
		button: number;
		ctrlKey: boolean;
		pointerType: string;

		constructor(type: string, props: PointerEventInit) {
			super(type, props);
			this.button = props.button || 0;
			this.ctrlKey = props.ctrlKey || false;
			this.pointerType = props.pointerType || "mouse";
		}
	}
	window.PointerEvent =
		MockPointerEvent as unknown as typeof window.PointerEvent;
	window.HTMLElement.prototype.scrollIntoView = vi.fn();
	window.HTMLElement.prototype.releasePointerCapture = vi.fn();
	window.HTMLElement.prototype.hasPointerCapture = vi.fn();
};
