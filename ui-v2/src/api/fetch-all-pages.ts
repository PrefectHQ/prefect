/**
 * Pages through a `/filter` endpoint until every row has been read.
 *
 * No `limit` is sent, so the server's configured
 * `PREFECT_SERVER_API_DEFAULT_LIMIT` decides the page size (an explicit limit
 * above it is rejected with a 422). The first page tells us that size; a
 * shorter page, or a page with nothing new, means we're done.
 */
export const fetchAllPages = async <T extends { id: string }>(
	fetchPage: (offset: number) => Promise<Array<T> | undefined>,
	startOffset = 0,
): Promise<Array<T>> => {
	const rows: Array<T> = [];
	const seen = new Set<string>();
	let offset = startOffset;
	let pageSize: number | undefined;
	for (;;) {
		const page = (await fetchPage(offset)) ?? [];
		const fresh = page.filter((row) => !seen.has(row.id));
		for (const row of fresh) {
			seen.add(row.id);
			rows.push(row);
		}
		pageSize ??= page.length;
		if (fresh.length === 0 || page.length < pageSize) {
			return rows;
		}
		offset += page.length;
	}
};
