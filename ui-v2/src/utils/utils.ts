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
	return plural || singular + "s";
};
