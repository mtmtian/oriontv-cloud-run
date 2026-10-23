import type { SearchResult } from './types';

/** Match spacing variants without mixing seasons, films or commentary. */
export async function searchExactTitle(
  query: string,
  search: (query: string) => Promise<SearchResult[]>
): Promise<SearchResult[]> {
  const compactQuery = query.replace(/\s+/g, '');
  if (!compactQuery) return [];

  const matches = (result: SearchResult) =>
    result.title.replace(/\s+/g, '') === compactQuery;
  const results = (await search(query)).filter(matches);
  if (results.length > 0 || query === compactQuery) return results;

  // Some providers treat whitespace as OR and bury the requested title.
  return (await search(compactQuery)).filter(matches);
}
