import { NextRequest, NextResponse } from 'next/server';

import { getConfig } from '@/lib/config';
import {
  mergePlaylists,
  PlaylistSource,
  tokenMatches,
} from '@/lib/live-playlist';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CACHE_MS = 30 * 60 * 1000;
const PARTIAL_CACHE_MS = 5 * 60 * 1000;
const FETCH_TIMEOUT_MS = 15 * 1000;
const MAX_LIST_CHARS = 5 * 1024 * 1024;
const DEFAULT_UA = 'AptvPlayer/1.4.10';

let cached: { key: string; body: string; expiresAt: number } | null = null;

async function fetchList(live: {
  name: string;
  url: string;
  ua?: string;
}): Promise<PlaylistSource | null> {
  try {
    const response = await fetch(live.url, {
      headers: { 'User-Agent': live.ua || DEFAULT_UA },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const text = await response.text();
    if (text.length > MAX_LIST_CHARS) return null;
    return { name: live.name, url: live.url, text };
  } catch {
    return null;
  }
}

// OrionTV loads one M3U URL and cannot send cookies, so the token travels in
// the query string. Do not log request URLs in this route.
export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token');
  if (!tokenMatches(token, process.env.LIVE_PLAYLIST_TOKEN)) {
    return new NextResponse('Not found', { status: 404 });
  }

  const config = await getConfig();
  const lives = (config.LiveConfig || []).filter((live) => !live.disabled);
  const key = JSON.stringify(lives.map((l) => [l.name, l.url, l.ua || '']));

  if (!cached || cached.key !== key || cached.expiresAt <= Date.now()) {
    const lists = (await Promise.all(lives.map(fetchList))).filter(
      (list): list is PlaylistSource => list !== null
    );
    if (lists.length === 0) {
      return new NextResponse('No live list is reachable', { status: 502 });
    }
    // Retry sooner when some upstream lists were unavailable.
    const ttl = lists.length === lives.length ? CACHE_MS : PARTIAL_CACHE_MS;
    cached = { key, body: mergePlaylists(lists), expiresAt: Date.now() + ttl };
  }

  return new NextResponse(cached.body, {
    headers: {
      'Content-Type': 'audio/x-mpegurl; charset=utf-8',
      'Cache-Control': 'private, no-store',
    },
  });
}
