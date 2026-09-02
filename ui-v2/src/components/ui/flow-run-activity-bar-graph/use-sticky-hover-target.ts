import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Tracks a hover target that lags behind the live `candidate`.
 *
 * The first candidate is adopted immediately. Any later change (including
 * the candidate disappearing) only takes effect after `switchDelay` ms have
 * passed without the candidate's key changing back. While pinned, candidate
 * changes are ignored entirely so the current target stays put.
 *
 * @param candidate - The element currently under the pointer, if any
 * @param getKey - Returns a stable identity for a candidate
 * @param switchDelay - Delay in milliseconds before adopting a new candidate
 */
export const useStickyHoverTarget = <T>(
	candidate: T | undefined,
	getKey: (target: T) => string,
	switchDelay = 150,
) => {
	const [target, setTarget] = useState<T | undefined>(candidate);
	const [isPinned, setIsPinned] = useState(false);
	const candidateRef = useRef(candidate);
	candidateRef.current = candidate;

	const candidateKey = candidate === undefined ? undefined : getKey(candidate);
	const targetKey = target === undefined ? undefined : getKey(target);

	useEffect(() => {
		if (isPinned || candidateKey === targetKey) {
			return;
		}
		if (targetKey === undefined) {
			setTarget(candidateRef.current);
			return;
		}
		const timer = setTimeout(() => {
			setTarget(candidateRef.current);
		}, switchDelay);
		return () => clearTimeout(timer);
	}, [isPinned, candidateKey, targetKey, switchDelay]);

	const pin = useCallback(() => setIsPinned(true), []);
	const unpin = useCallback(() => setIsPinned(false), []);

	return { target, isPinned, pin, unpin };
};
