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

/**
 * The global localStorage mock discards writes. Call this to back it with
 * memory for a test that reads back what it stored, and call the returned
 * function afterwards to restore the no-op behavior.
 */
export const mockInMemoryLocalStorage = () => {
	const items = new Map<string, string>();
	const spies = [
		vi
			.spyOn(localStorage, "getItem")
			.mockImplementation((key) => items.get(key) ?? null),
		vi.spyOn(localStorage, "setItem").mockImplementation((key, value) => {
			items.set(key, value);
		}),
		vi.spyOn(localStorage, "removeItem").mockImplementation((key) => {
			items.delete(key);
		}),
	];
	return () => {
		for (const spy of spies) {
			spy.mockReset();
		}
	};
};
