import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges class names using clsx and tailwind-merge
 *
 * @param inputs Class name values to merge
 * @returns Merged class name string with Tailwind conflicts resolved
 *
 * @example
 * ```ts
 * // Merges class names and resolves Tailwind conflicts
 * cn("px-2 py-1", "p-3"); // returns "p-3"
 * cn("bg-red-500", "bg-blue-500"); // returns "bg-blue-500"
 * cn("text-sm md:text-lg", "md:text-xl"); // returns "text-sm md:text-xl"
 * ```
 */
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

/**
 * Checks if an array starts with a given prefix array
 *
 * @param array The array to check
 * @param prefix The prefix array to check against
 * @returns True if array starts with prefix, false otherwise
 *
 * @example
 * ```ts
 * const array = [1, 2, 3, 4];
 * const prefix = [1, 2];
 * startsWith(array, prefix); // returns true
 *
 * const notPrefix = [2, 3];
 * startsWith(array, notPrefix); // returns false
 * ```
 */
export function startsWith(
	array: readonly unknown[],
	prefix: readonly unknown[],
) {
	return prefix.every((item, index) => array[index] === item);
}
