import assert from 'node:assert/strict';
import test from 'node:test';

import { searchExactTitle } from '../src/lib/exact-title-search.ts';

const episode = (title) => ({
  id: '1', title, poster: '', episodes: ['https://example.com/1.m3u8'],
  episodes_titles: ['第1集'], source: 'test', source_name: 'Test', year: '2008',
});

test('matches source spacing variants but excludes other seasons and commentary', async () => {
  const expected = episode('绝命毒师  第一季');
  const rows = [expected, episode('绝命毒师第二季'),
    episode('绝命毒师第一季[电影解说]'), episode('续命之徒：绝命毒师电影')];
  const calls = [];
  const results = await searchExactTitle('绝命毒师第一季', async (q) => {
    calls.push(q);
    return rows;
  });
  assert.deepEqual(results, [expected]);
  assert.deepEqual(calls, ['绝命毒师第一季']);
});

test('retries a compact query when a provider treats spaces as OR', async () => {
  const expected = episode('绝命毒师 第一季');
  const calls = [];
  const results = await searchExactTitle('绝命毒师 第一季', async (q) => {
    calls.push(q);
    return q.includes(' ') ? [episode('其他剧第一季')] : [expected];
  });
  assert.deepEqual(results, [expected]);
  assert.deepEqual(calls, ['绝命毒师 第一季', '绝命毒师第一季']);
});

test('keeps all matching results and avoids a redundant fallback', async () => {
  const rows = [episode('绝命毒师 第一季'), episode('绝命毒师第一季')];
  let calls = 0;
  assert.deepEqual(await searchExactTitle('绝命毒师 第一季', async () => {
    calls++;
    return rows;
  }), rows);
  assert.equal(calls, 1);
});

test('returns no matches for a bare series name and does not repeat identical queries', async () => {
  let calls = 0;
  assert.deepEqual(await searchExactTitle('绝命毒师', async () => {
    calls++;
    return [episode('绝命毒师第一季')];
  }), []);
  assert.equal(calls, 1);
});

test('handles Unicode whitespace without accepting a different title', async () => {
  const row = episode('绝命毒师\u3000第一季');
  assert.deepEqual(await searchExactTitle(' 绝命毒师\t第一季 ', async () => [row]), [row]);
  assert.deepEqual(await searchExactTitle('绝命毒师 第一季', async () => [episode('绝命毒师第二季')]), []);
});

test('does not send an empty title upstream', async () => {
  assert.deepEqual(await searchExactTitle(' \t ', async () => {
    assert.fail('upstream must not be called');
  }), []);
});

test('propagates upstream failures to the route error handler', async () => {
  await assert.rejects(searchExactTitle('绝命毒师第一季', async () => {
    throw new Error('upstream failed');
  }), /upstream failed/);
});
