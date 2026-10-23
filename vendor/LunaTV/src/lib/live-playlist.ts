import { createHash, timingSafeEqual } from 'node:crypto';

export interface PlaylistSource {
  name: string;
  /** URL the text was served from, after redirects. */
  url: string;
  text: string;
}

const GROUP_ATTR = /group-title="([^"]*)"/i;

// iptv-org groups are global English categories such as "General"; one group
// per list is easier to browse with a remote. Other lists keep their groups.
function keepsOwnGroups(url: string): boolean {
  return !url.startsWith('https://iptv-org.github.io/');
}

function withGroup(extinf: string, group: string): string {
  const attr = `group-title="${group.replace(/"/g, '')}"`;
  // A replacer function keeps `$&`-style patterns in list names literal.
  if (GROUP_ATTR.test(extinf)) return extinf.replace(GROUP_ATTR, () => attr);
  // The first comma outside quotes ends the attribute list.
  let quoted = false;
  for (let i = 0; i < extinf.length; i++) {
    if (extinf[i] === '"') quoted = !quoted;
    else if (extinf[i] === ',' && !quoted) {
      return `${extinf.slice(0, i)} ${attr}${extinf.slice(i)}`;
    }
  }
  return extinf;
}

/** A download counts only if it has at least one channel entry. */
export function isPlaylist(text: string): boolean {
  return text.includes('#EXTINF:');
}

// The TV would resolve a relative reference against this backend, so resolve
// it against the URL the list was served from. Absolute URLs stay byte-for-byte.
function streamUrl(line: string, listUrl: string): string | null {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(line)) return line;
  try {
    return new URL(line, listUrl).href;
  } catch {
    return null;
  }
}

/** Merge M3U lists in order; a stream URL seen earlier is not repeated. */
export function mergePlaylists(sources: PlaylistSource[]): string {
  const seen = new Set<string>();
  const out = ['#EXTM3U'];
  for (const source of sources) {
    const ownGroups = keepsOwnGroups(source.url);
    let entry: string[] | null = null;
    for (const raw of source.text.split(/\r?\n/)) {
      const line = raw.trim();
      if (line.startsWith('#EXTINF:')) {
        const group = line.match(GROUP_ATTR)?.[1].trim();
        entry = [ownGroups && group ? line : withGroup(line, source.name)];
      } else if (!entry || !line) {
        continue;
      } else if (line.startsWith('#')) {
        if (!line.startsWith('#EXTM3U')) entry.push(line);
      } else {
        const url = streamUrl(line, source.url);
        if (url && !seen.has(url)) {
          seen.add(url);
          out.push(...entry, url);
        }
        entry = null;
      }
    }
  }
  return `${out.join('\n')}\n`;
}

/** Constant-time comparison; an unset expected token rejects every request. */
export function tokenMatches(
  given: string | null,
  expected: string | undefined
): boolean {
  if (!given || !expected) return false;
  const digest = (value: string) => createHash('sha256').update(value).digest();
  return timingSafeEqual(digest(given), digest(expected));
}
