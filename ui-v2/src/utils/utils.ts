/**
 *
 * @param str
 * @returns a string to a capitalized format.
 *
 * @example
 * ```ts;
 * const x = capitalize("hello World") // Hello world
 * ```
 */
export const capitalize = (str: string) => {
	return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

/**
 *
 * @param str
 * @returns a pluralized string based on the count
 *
 * @example
 * ```ts;
 * const fruits = ["apple", "banana"]
 * const x = pluralize(fruits.length, "fruit") // Fruits
 * ```
 */
export const pluralize = (
	count: number,
	singular: string,
	plural?: string,
): string => {
	if (count === 1) {
		return singular;
	}
	return plural || `${singular}s`;
};

/**
 * Converts a string to title case format by capitalizing first letters
 * and converting underscores/hyphens to spaces
 *
 * @param str - The string to convert to title case
 * @returns A title case formatted string
 *
 * @example
 * ```ts
 * const result = titleCase("hello_world-test") // "Hello World Test"
 * ```
 */
export const titleCase = (str: string): string => {
	return str
		.replace(/^[-_]*(.)/, (_match, char: string) => char.toUpperCase())
		.replace(/[-_]+(.)/g, (_match, char: string) => ` ${char.toUpperCase()}`);
};

type TupleType<T extends unknown[]> = {
	values: Readonly<T>;
	isValue: (value: unknown) => value is T[number];
};

/**
 * Creates a tuple with the provided values.
 *
 * @template T - The type of the elements in the tuple.
 * @param {T} values - The values to be included in the tuple.
 * @returns {TupleType<T>} An object representing the tuple, with a `values` property containing the tuple values and an `isValue` method to check if a value is part of the tuple.
 */
export function createTuple<const T extends unknown[]>(
	values: T,
): TupleType<T> {
	const tuple = new Set(values);

	function isValue(value: unknown): value is T[number] {
		return tuple.has(value);
	}

	return {
		values,
		isValue,
	};
}
