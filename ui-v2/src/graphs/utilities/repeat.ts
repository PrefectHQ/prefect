export function repeat<T>(length: number, method: (index: number) => T): T[] {
	return Array.from({ length }, (_element, index) => method(index));
}
