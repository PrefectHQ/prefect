import { type RefObject, useLayoutEffect, useRef } from "react";

const DURATION_MS = 200;
const ITEM_SELECTOR = "[data-reorder-id]";

/**
 * Animates the children of `containerRef` to their new positions when their
 * order changes, instead of letting them jump. Children opt in with a
 * `data-reorder-id` attribute that is stable across renders; children that
 * were not rendered before are left alone. Does nothing when the user prefers
 * reduced motion.
 *
 * @param containerRef - element whose `data-reorder-id` descendants are animated
 * @param order - the ids in rendered order; positions are re-measured when it changes
 * @param enabled - set to false to skip measuring and animating
 *
 * @example
 * ```tsx
 * const listRef = useRef<HTMLUListElement>(null);
 * useAnimatedReorder(listRef, items.map((item) => item.id));
 * return (
 *   <ul ref={listRef}>
 *     {items.map((item) => (
 *       <li key={item.id} data-reorder-id={item.id}>{item.name}</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useAnimatedReorder(
	containerRef: RefObject<HTMLElement | null>,
	order: readonly string[],
	enabled = true,
) {
	const previousTops = useRef(new Map<string, number>());
	const orderKey = order.join("\n");

	// biome-ignore lint/correctness/useExhaustiveDependencies: orderKey is what signals that positions may have changed
	useLayoutEffect(() => {
		const container = containerRef.current;
		if (!enabled || !container) {
			previousTops.current = new Map();
			return;
		}

		const items = [...container.querySelectorAll<HTMLElement>(ITEM_SELECTOR)];
		for (const item of items) {
			for (const animation of item.getAnimations?.() ?? []) {
				animation.cancel();
			}
		}

		const containerTop = container.getBoundingClientRect().top;
		const tops = new Map<string, number>();
		for (const item of items) {
			const id = item.dataset.reorderId;
			if (id !== undefined) {
				tops.set(id, item.getBoundingClientRect().top - containerTop);
			}
		}

		const reduceMotion = window.matchMedia?.(
			"(prefers-reduced-motion: reduce)",
		).matches;
		if (!reduceMotion) {
			for (const item of items) {
				const id = item.dataset.reorderId;
				const previousTop =
					id === undefined ? undefined : previousTops.current.get(id);
				const top = id === undefined ? undefined : tops.get(id);
				if (previousTop === undefined || top === undefined) continue;
				const delta = previousTop - top;
				if (delta === 0) continue;
				item.animate?.(
					[
						{ transform: `translateY(${delta}px)` },
						{ transform: "translateY(0)" },
					],
					{ duration: DURATION_MS, easing: "ease-out" },
				);
			}
		}

		previousTops.current = tops;
	}, [containerRef, orderKey, enabled]);
}
