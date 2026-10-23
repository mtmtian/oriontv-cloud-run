/* eslint-disable no-console */

import { NextRequest, NextResponse } from 'next/server';

import { getConfig } from '@/lib/config';
import { defaultUA } from '@/lib/live';
import {
  type PlaylistSource,
  isPlaylist,
  mergePlaylists,
  tokenMatches,
} from '@/lib/live-playlist';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CACHE_MS = 30 * 60 * 1000;
const PARTIAL_CACHE_MS = 5 * 60 * 1000;
const FETCH_TIMEOUT_MS = 15 * 1000;
const MAX_LIST_BYTES = 5 * 1024 * 1024;

type Live = { key: string; name: string; url: string; ua?: string };

let cached: { key: string; body: string; expiresAt: number } | null = null;
// Last valid download per configured URL, used when a refresh of that list fails.
const lastGood = new Map<string, PlaylistSource>();

async function readCapped(response: Response): Promise<string | null> {
  const reader = response.body?.getReader();
  if (!reader) return null;
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_LIST_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString('utf8');
}

async function download(live: Live): Promise<PlaylistSource | null> {
  try {
    const response = await fetch(live.url, {
      headers: { 'User-Agent': live.ua || defaultUA },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    const text = response.ok ? await readCapped(response) : null;
    // A 200 maintenance or login page must not replace the last good copy.
    if (text === null || !isPlaylist(text)) {
      console.warn(`live playlist ${live.key}: HTTP ${response.status}, oversized or not a playlist`);
      return null;
    }
    // Relative stream references resolve against the URL after redirects.
    return { name: live.name, url: response.url || live.url, text };
  } catch (error) {
    console.warn(`live playlist ${live.key}: ${(error as Error).name}`);
    return null;
  }
}

// OrionTV loads one M3U URL and cannot send cookies, so the token travels in
// the query string. Do not log request URLs in this route.
export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token');
  if (!tokenMatches(token, process.env.LIVE_PLAYLIST_TOKEN?.trim())) {
    return new NextResponse('Not found', { status: 404 });
  }

  const config = await getConfig();
  const lives: Live[] = (config.LiveConfig || []).filter((l) => !l.disabled);
  const key = JSON.stringify(lives.map((l) => [l.name, l.url, l.ua || '']));

  if (!cached || cached.key !== key || cached.expiresAt <= Date.now()) {
    const downloads = await Promise.all(lives.map(download));
    const lists: PlaylistSource[] = [];
    downloads.forEach((list, i) => {
      const { name, url } = lives[i];
      if (list) lastGood.set(url, list);
      const usable = list ?? lastGood.get(url);
      if (usable) lists.push({ ...usable, name });
    });
    if (lives.length > 0 && lists.length === 0) {
      return new NextResponse('No live list is reachable', { status: 502 });
    }
    // Retry sooner when some lists were missing or served from the last good copy.
    const complete = downloads.every((list) => list !== null);
    cached = {
      key,
      body: mergePlaylists(lists),
      expiresAt: Date.now() + (complete ? CACHE_MS : PARTIAL_CACHE_MS),
    };
  }

  return new NextResponse(cached.body, {
    headers: {
      'Content-Type': 'audio/x-mpegurl; charset=utf-8',
      'Cache-Control': 'private, no-store',
    },
  });
}
