import { useEffect, useState } from "react";

/**
 *
 * @param key local storage key
 * @param initialValue initial value of stored state
 * @returns a hook to synchronize state with local storage
 *
 * @example
 * ```ts
 * function MyComponent() {
 *   const [name, setName] = useLocalStorage<string>('name', '');
 *   return (
 *     <div>
 *       <input type="text" value={name} onChange={e => setName(e.target.value)} />
 *       <p>Hello, {name}!</p>
 *     </div>
 *   );
 * }
 * ```
 */
export function useLocalStorage<T>(
	key: string,
	initialValue: T,
): [T, (value: T | ((prevValue: T) => T)) => void] {
	const [storedValue, setStoredValue] = useState<T>(() => {
		if (typeof window !== "undefined") {
			try {
				const item = localStorage.getItem(key);
				return item ? (JSON.parse(item) as T) : initialValue;
			} catch (error) {
				console.log(error);
				return initialValue;
			}
		} else {
			return initialValue;
		}
	});

	useEffect(() => {
		if (typeof window !== "undefined") {
			localStorage.setItem(key, JSON.stringify(storedValue));
		}
	}, [key, storedValue]);

	return [storedValue, setStoredValue];
}
