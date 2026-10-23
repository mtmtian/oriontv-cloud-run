import assert from 'node:assert/strict';
import test from 'node:test';

import { mergePlaylists, tokenMatches } from '../src/lib/live-playlist.ts';

const guovin = {
  name: 'Guovin',
  url: 'https://guovin.github.io/iptv-api/ipv4.m3u',
  text: [
    '#EXTM3U x-tvg-url="https://guovin.github.io/iptv-api/epg.gz"',
    '#EXTINF:-1 tvg-id="CCTV-1" group-title="📺央视频道",CCTV-1',
    'http://a.example/cctv1.m3u8',
    '#EXTINF:-1 tvg-id="CCTV-1" group-title="📺央视频道",CCTV-1',
    'http://a.example/cctv1.m3u8',
    '#EXTINF:-1 tvg-id="X",No group',
    'http://a.example/x.m3u8',
  ].join('\r\n'),
};

const taiwan = {
  name: 'iptv-org 台湾频道',
  url: 'https://iptv-org.github.io/iptv/countries/tw.m3u',
  text: [
    '#EXTM3U',
    '#EXTINF:-1 tvg-id="CTS.tw" group-title="General",CTS (1080p)',
    '#EXTVLCOPT:http-referrer=https://cts.example/',
    'https://b.example/cts.m3u8',
    '#EXTINF:-1 tvg-id="TTV.tw" tvg-name="TTV, Taiwan",TTV',
    'https://b.example/ttv.m3u8',
  ].join('\n'),
};

const chinese = {
  name: 'iptv-org 中文频道',
  url: 'https://iptv-org.github.io/iptv/languages/zho.m3u',
  text: [
    '#EXTM3U',
    '#EXTINF:-1 group-title="General",CTS (1080p)',
    'https://b.example/cts.m3u8',
    '#EXTINF:-1 group-title="News",CCTV-1',
    'http://a.example/cctv1.m3u8',
    '#EXTINF:-1 group-title="News",Channel 8',
    'https://c.example/ch8.m3u8',
  ].join('\n'),
};

test('keeps curated groups, groups iptv-org by list and drops repeated URLs', () => {
  assert.equal(
    mergePlaylists([guovin, taiwan, chinese]),
    [
      '#EXTM3U',
      '#EXTINF:-1 tvg-id="CCTV-1" group-title="📺央视频道",CCTV-1',
      'http://a.example/cctv1.m3u8',
      '#EXTINF:-1 tvg-id="X" group-title="Guovin",No group',
      'http://a.example/x.m3u8',
      '#EXTINF:-1 tvg-id="CTS.tw" group-title="iptv-org 台湾频道",CTS (1080p)',
      '#EXTVLCOPT:http-referrer=https://cts.example/',
      'https://b.example/cts.m3u8',
      '#EXTINF:-1 tvg-id="TTV.tw" tvg-name="TTV, Taiwan" group-title="iptv-org 台湾频道",TTV',
      'https://b.example/ttv.m3u8',
      '#EXTINF:-1 group-title="iptv-org 中文频道",Channel 8',
      'https://c.example/ch8.m3u8',
      '',
    ].join('\n')
  );
});

test('removes quotes from list names used as groups', () => {
  const merged = mergePlaylists([{ ...taiwan, name: 'My "TW" list' }]);
  assert.match(merged, /group-title="My TW list",CTS/);
});

test('ignores entries without a stream URL', () => {
  const merged = mergePlaylists([
    { ...guovin, text: '#EXTINF:-1,Broken\n#EXTINF:-1,Fine\nhttp://a.example/fine.m3u8' },
  ]);
  assert.equal(
    merged,
    '#EXTM3U\n#EXTINF:-1 group-title="Guovin",Fine\nhttp://a.example/fine.m3u8\n'
  );
});

test('token check rejects missing, unset and wrong tokens', () => {
  assert.equal(tokenMatches('secret-token', 'secret-token'), true);
  assert.equal(tokenMatches('secret-tokem', 'secret-token'), false);
  assert.equal(tokenMatches('short', 'secret-token'), false);
  assert.equal(tokenMatches(null, 'secret-token'), false);
  assert.equal(tokenMatches('secret-token', undefined), false);
  assert.equal(tokenMatches('', ''), false);
});
