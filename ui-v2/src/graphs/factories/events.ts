// need to use any for function arguments
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Handler<T = any> = (...payload: T[]) => void;
type Events = Record<string, unknown>;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function eventsFactory<T extends Events>() {
	type Event = keyof T;
	type Handlers = Set<Handler>;
	const all = new Map<Event, Handlers>();

	function on<E extends Event>(event: E, handler: Handler<T[E]>): () => void {
		const existing = all.get(event);

		if (existing) {
			existing.add(handler);
		} else {
			all.set(event, new Set([handler]));
		}

		return () => off(event, handler);
	}

	function once<E extends Event>(event: E, handler: Handler<T[E]>): void {
		const callback: Handler<T[E]> = (args) => {
			off(event, callback);
			handler(args);
		};

		on(event, callback);
	}

	function off<E extends Event>(event: E, handler: Handler<T[E]>): void {
		all.get(event)?.delete(handler);
	}

	function emit<E extends Event>(
		event: undefined extends T[E] ? E : never,
	): void;
	function emit<E extends Event>(event: E, payload: T[E]): void;
	function emit<E extends Event>(event: E, payload?: T[E]): void {
		all.get(event)?.forEach((handler) => handler(payload));
	}

	function clear(): void {
		all.clear();
	}

	return {
		on,
		off,
		once,
		emit,
		clear,
	};
}
