import { render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAnimatedReorder } from "./use-animated-reorder";

const ROW_HEIGHT = 50;

const List = ({ ids, enabled }: { ids: string[]; enabled?: boolean }) => {
	const ref = useRef<HTMLUListElement>(null);
	useAnimatedReorder(ref, ids, enabled);
	return (
		<ul ref={ref}>
			{ids.map((id) => (
				<li key={id} data-reorder-id={id}>
					{id}
				</li>
			))}
		</ul>
	);
};

describe("useAnimatedReorder", () => {
	let animations: {
		id: string | undefined;
		from: string | undefined;
		options: KeyframeAnimationOptions;
	}[] = [];
	let prefersReducedMotion = false;

	beforeEach(() => {
		prefersReducedMotion = false;
		// jsdom has no layout, so place each item by its index in the list
		vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(
			function (this: Element) {
				const index = this.parentElement
					? [...this.parentElement.children].indexOf(this)
					: 0;
				const top = this.tagName === "LI" ? index * ROW_HEIGHT : 0;
				return new DOMRect(0, top, 100, ROW_HEIGHT);
			},
		);
		animations = [];
		HTMLElement.prototype.animate = function (
			this: HTMLElement,
			keyframes: Keyframe[],
			options: KeyframeAnimationOptions,
		) {
			animations.push({
				id: this.dataset.reorderId,
				from: keyframes[0]?.transform?.toString(),
				options,
			});
			return new EventTarget();
		} as HTMLElement["animate"];
		vi.stubGlobal("matchMedia", (query: string) => ({
			matches: query.includes("prefers-reduced-motion") && prefersReducedMotion,
		}));
	});

	afterEach(() => {
		vi.restoreAllMocks();
		vi.unstubAllGlobals();
	});

	const animatedItems = (): Record<string, string | undefined> =>
		Object.fromEntries(animations.map(({ id, from }) => [id ?? "", from]));

	it("does not animate the first render", () => {
		render(<List ids={["a", "b", "c"]} />);

		expect(animations).toEqual([]);
	});

	it("slides every item that moved from its previous position", () => {
		const { rerender } = render(<List ids={["a", "b", "c"]} />);

		rerender(<List ids={["c", "a", "b"]} />);

		expect(animatedItems()).toEqual({
			c: "translateY(100px)",
			a: "translateY(-50px)",
			b: "translateY(-50px)",
		});
		expect(animations[0]?.options).toEqual({
			duration: 200,
			easing: "ease-out",
		});
	});

	it("leaves items that did not move and items that are new alone", () => {
		const { rerender } = render(<List ids={["a", "b", "c"]} />);

		rerender(<List ids={["a", "c", "b", "d"]} />);

		expect(animatedItems()).toEqual({
			c: "translateY(50px)",
			b: "translateY(-50px)",
		});
	});

	it("does not animate when the user prefers reduced motion", () => {
		prefersReducedMotion = true;
		const { rerender } = render(<List ids={["a", "b"]} />);

		rerender(<List ids={["b", "a"]} />);

		expect(animations).toEqual([]);
	});

	it("does not animate when disabled", () => {
		const { rerender } = render(<List ids={["a", "b"]} enabled={false} />);

		rerender(<List ids={["b", "a"]} enabled={false} />);

		expect(animations).toEqual([]);
	});
});
