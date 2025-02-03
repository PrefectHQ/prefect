import { expect, test } from "vitest";
import { capitalize, pluralize } from "./utils";

test("capitalize", () => {
	const TEST_STRING = "teststring";

	const RESULT = capitalize(TEST_STRING);
	const EXPECTED = "Teststring";

	expect(RESULT).toEqual(EXPECTED);
});

test("pluralize -- single", () => {
	const FRUITS = ["apple"];

	const RESULT = pluralize(FRUITS.length, "Fruit");
	const EXPECTED = "Fruit";

	expect(RESULT).toEqual(EXPECTED);
});

test("pluralize -- plural", () => {
	const FRUITS = ["apple", "banana"];

	const RESULT = pluralize(FRUITS.length, "Fruit");
	const EXPECTED = "Fruits";

	expect(RESULT).toEqual(EXPECTED);
});

test("pluralize -- custom pluralization", () => {
	const FRUITS = ["Alice", "Bob"];

	const RESULT = pluralize(FRUITS.length, "child", "children");
	const EXPECTED = "children";

	expect(RESULT).toEqual(EXPECTED);
});
