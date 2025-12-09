import { useEffect, useState } from "react";

type UseNowOptions = {
	/**
	 * The interval in milliseconds at which to update the current time
	 * @default 1000
	 */
	interval?: number;
};

/**
 * A hook that returns the current time and updates it at a specified interval.
 * Useful for live-updating relative time displays.
 *
 * @param options - Configuration options
 * @returns The current Date object, updated at the specified interval
 *
 * @example
 * ```tsx
 * const now = useNow({ interval: 1000 });
 * const relativeTime = formatDateTimeRelative(someDate, now);
 * ```
 */
export function useNow({ interval = 1000 }: UseNowOptions = {}): Date {
	const [now, setNow] = useState(() => new Date());

	useEffect(() => {
		const timer = setInterval(() => {
			setNow(new Date());
		}, interval);

		return () => clearInterval(timer);
	}, [interval]);

	return now;
}
