import type { TestingLibraryMatchers } from "@testing-library/jest-dom/matchers";

// Remove when jest-dom supports Vitest 5: https://github.com/testing-library/jest-dom/issues/738
declare module "vitest" {
	interface Matchers<R, T> extends TestingLibraryMatchers<T, R> {}
}
