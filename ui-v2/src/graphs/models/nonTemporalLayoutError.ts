export class NonTemporalLayoutError extends Error {
	public constructor() {
		super("Layout is not temporal");
	}
}
