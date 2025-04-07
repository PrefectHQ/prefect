import { vi } from "vitest";

vi.mock("@/hooks/use-debounce", () => ({
	default: (v: unknown) => v,
}));
