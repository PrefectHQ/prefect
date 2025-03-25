/* eslint-disable @typescript-eslint/unbound-method */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useLocalStorage } from "./use-local-storage";

describe("useLocalStorage ", () => {
	it("is able to synchronize state with local storage", () => {
		// TEST
		const { result } = renderHook(() => useLocalStorage("name", ""));
		const [, setState] = result.current;

		expect(localStorage.getItem).toBeCalledWith("name");

		act(() => setState("new value"));
		const [nextState] = result.current;

		// nb: appends a set of "" when storing in local storage
		expect(nextState).toEqual("new value");
		expect(localStorage.setItem).toBeCalledWith("name", '"new value"');
	});
});
