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
