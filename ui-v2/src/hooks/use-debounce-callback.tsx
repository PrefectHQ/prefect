import { useCallback, useRef } from "react";

/**
 * A custom hook that returns a debounced version of the callback function.
 * The debounced function will only execute after the specified delay has passed
 * without the function being called again.
 *
 * @template Args - The tuple type representing the arguments of the callback
 * @template R - The return type of the callback
 * @param {(...args: Args) => R} callback - The function to debounce
 * @param {number} delay - The delay in milliseconds
 * @param {boolean} [leading=false] - Whether to call the function on the leading edge
 * @returns {(...args: Args) => void} - The debounced callback function
 */
const useDebounceCallback = <Args extends unknown[], R>(
	callback: (...args: Args) => R,
	delay: number,
	leading = false,
): ((...args: Args) => void) => {
	const timeoutRef = useRef<NodeJS.Timeout | null>(null);
	const callbackRef = useRef<(...args: Args) => R>(callback);
	const leadingCallRef = useRef<boolean>(true);

	// Update the callback reference when it changes
	callbackRef.current = callback;

	return useCallback(
		(...args: Args) => {
			const invokeFunction = () => {
				callbackRef.current(...args);
				leadingCallRef.current = true;
			};

			// Clear any existing timeout
			if (timeoutRef.current) {
				clearTimeout(timeoutRef.current);
			}

			// Handle leading edge calls
			if (leading && leadingCallRef.current) {
				invokeFunction();
				leadingCallRef.current = false;
			} else {
				// Set new timeout for trailing edge
				timeoutRef.current = setTimeout(() => {
					if (!leading) {
						invokeFunction();
					}
					leadingCallRef.current = true;
				}, delay);
			}
		},
		[delay, leading],
	);
};

export default useDebounceCallback;

// Example usage with strict types:

// type SearchProps {
//   onSearch: (term: string) => Promise<void>;
// }

// const SearchComponent: React.FC<SearchProps> = ({ onSearch }) => {
//   // Type inference works automatically
//   const debouncedSearch = useDebounceCallback(onSearch, 500);

//   // Multiple parameters example
//   const handleMultiParam = (id: number, value: string) => {
//     console.log(id, value);
//   };
//   const debouncedMultiParam = useDebounceCallback(handleMultiParam, 500);

//   return (
//     <div>
//       <input
//         type="text"
//         onChange={(e) => debouncedSearch(e.target.value)}
//         placeholder="Search..."
//       />
//       <button onClick={() => debouncedMultiParam(1, "test")}>
//         Test Multi Param
//       </button>
//     </div>
//   );
// };
