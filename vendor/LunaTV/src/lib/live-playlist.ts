import { createHash, timingSafeEqual } from 'node:crypto';

export interface PlaylistSource {
  name: string;
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
  if (GROUP_ATTR.test(extinf)) return extinf.replace(GROUP_ATTR, attr);
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
      } else if (line.includes('://')) {
        if (!seen.has(line)) {
          seen.add(line);
          out.push(...entry, line);
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
