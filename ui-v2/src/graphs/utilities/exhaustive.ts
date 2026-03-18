export function exhaustive(value: never): void {
	throw new Error(`switch does not have case for value: ${value}`);
}
