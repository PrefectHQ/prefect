import { expect, test } from "vitest";
import { capitalize, pluralize, titleCase } from "./utils";

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

test("titleCase -- basic conversion", () => {
	const TEST_STRING = "hello_world";
	const RESULT = titleCase(TEST_STRING);
	const EXPECTED = "Hello World";

	expect(RESULT).toEqual(EXPECTED);
});

test("titleCase -- with hyphens", () => {
	const TEST_STRING = "test-case-example";
	const RESULT = titleCase(TEST_STRING);
	const EXPECTED = "Test Case Example";

	expect(RESULT).toEqual(EXPECTED);
});

test("titleCase -- mixed delimiters", () => {
	const TEST_STRING = "_hello-world_test";
	const RESULT = titleCase(TEST_STRING);
	const EXPECTED = "Hello World Test";

	expect(RESULT).toEqual(EXPECTED);
});

test("titleCase -- single word", () => {
	const TEST_STRING = "process";
	const RESULT = titleCase(TEST_STRING);
	const EXPECTED = "Process";

	expect(RESULT).toEqual(EXPECTED);
});

test("pluralize -- custom pluralization", () => {
	const FRUITS = ["Alice", "Bob"];

	const RESULT = pluralize(FRUITS.length, "child", "children");
	const EXPECTED = "children";

	expect(RESULT).toEqual(EXPECTED);
});
