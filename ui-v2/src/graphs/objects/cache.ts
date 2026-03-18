type Action = (...args: any[]) => any;

// Using any here because there isn't much benefit in typing this cache store. The key determines what type of value is returned.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let caches = new Map<string, any>();

export function startCache(): void {
	// do nothing
}

export function stopCache(): void {
	caches = new Map();
}

export async function cache<T extends Action>(
	action: T,
	parameters: Parameters<T>,
): Promise<ReturnType<T>> {
	const key = `${action.toString()}-${JSON.stringify(parameters)}`;

	if (caches.has(key)) {
		return caches.get(key);
	}

	const value = await action(...parameters);

	caches.set(key, value);

	return value;
}
