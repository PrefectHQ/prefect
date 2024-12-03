import { useCallback, useMemo, useState } from "react";

type StableActions<K> = {
	add: (key: K) => void;
	remove: (key: K) => void;
	toggle: (key: K) => void;
	reset: () => void;
	clear: () => void;
};

type Actions<K> = StableActions<K> & {
	has: (key: K) => boolean;
};

/**
 * A hook that is used to declarative to keep state of a 'Set' type of data structure.
 * This is useful in cases where the UX needs to keep track of selected rows by id
 *
 * @param initialSet Initial state of a Set
 * @returns a Set object and utils as a tuple
 *
 * @example
 * ```tsx
 * function FlowCheckboxList() {
 *   const [selectedIDs, { has, toggle }] = useSet<string>();
 *
 *   return flows.map((flow) =>
 * 		<Checkbox
 * 			key={flow.id}
 * 			checked={has(flow.id)}
 * 			onCheck={() => toggle(flow.id)}
 * 			label={flow.name} />
 *
 * }
 * ```
 */
export const useSet = <K>(initialSet = new Set<K>()): [Set<K>, Actions<K>] => {
	const [set, setSet] = useState(initialSet);

	const stableActions = useMemo(() => {
		const add = (item: K) =>
			setSet((curr) => new Set([...Array.from(curr), item]));
		const remove = (item: K) =>
			setSet(
				(curr) => new Set([...Array.from(curr).filter((i) => i !== item)]),
			);
		const toggle = (item: K) =>
			setSet((curr) =>
				curr.has(item)
					? new Set(Array.from(curr).filter((i) => i !== item))
					: new Set([...Array.from(curr), item]),
			);
		const reset = () => setSet(initialSet);
		const clear = () => setSet(new Set());

		return { add, remove, toggle, clear, reset };
	}, [initialSet]);

	const utils = {
		has: useCallback((item) => set.has(item), [set]),
		...stableActions,
	} as Actions<K>;

	return [set, utils];
};
