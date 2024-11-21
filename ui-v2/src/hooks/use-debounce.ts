import { useEffect, useState } from "react";

/**
 * A hook that returns a debounced value that only updates after a specified delay
 * has passed since the last change.
 *
 * @param value The value to debounce
 * @param delay The delay in milliseconds before the value updates (default: 500ms)
 * @returns The debounced value
 *
 * @example
 * ```tsx
 * function SearchInput() {
 *   const [searchTerm, setSearchTerm] = useState('');
 *   const debouncedSearch = useDebounce(searchTerm, 500);
 *
 *   useEffect(() => {
 *     // This will only run 500ms after the user stops typing
 *     searchAPI(debouncedSearch);
 *   }, [debouncedSearch]);
 *
 *   return (
 *     <input
 *       value={searchTerm}
 *       onChange={(e) => setSearchTerm(e.target.value)}
 *     />
 *   );
 * }
 * ```
 */
function useDebounce<T>(value: T, delay = 500): T {
	const [debouncedValue, setDebouncedValue] = useState<T>(value);

	useEffect(() => {
		const timer = setTimeout(() => {
			setDebouncedValue(value);
		}, delay);

		return () => {
			clearTimeout(timer);
		};
	}, [value, delay]);

	return debouncedValue;
}

export default useDebounce;
