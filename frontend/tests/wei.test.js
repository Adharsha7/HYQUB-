/**
 * HYQUB — wei.js unit tests
 * Run with: node --test tests/wei.test.js
 */

import { strict as assert } from 'node:assert';
import { test, describe } from 'node:test';
import { parseEthToWei, weiToEthString, isValidWeiString, compareWei, buildSubmitBody } from '../js/wei.js';

// ─── parseEthToWei ────────────────────────────────────────────────────────────

describe('parseEthToWei — valid inputs', () => {
  test('"1" → 1000000000000000000', () => {
    assert.strictEqual(parseEthToWei('1'), '1000000000000000000');
  });

  test('"0.1" → 100000000000000000', () => {
    assert.strictEqual(parseEthToWei('0.1'), '100000000000000000');
  });

  test('"0.000000000000000001" → 1 (1 wei)', () => {
    assert.strictEqual(parseEthToWei('0.000000000000000001'), '1');
  });

  test('"123456789.123456789012345678" → correct BigInt string', () => {
    assert.strictEqual(
      parseEthToWei('123456789.123456789012345678'),
      '123456789123456789012345678'
    );
  });

  test('"0.5" → 500000000000000000', () => {
    assert.strictEqual(parseEthToWei('0.5'), '500000000000000000');
  });

  test('"10" → 10000000000000000000', () => {
    assert.strictEqual(parseEthToWei('10'), '10000000000000000000');
  });

  test('"0.123456789012345678" → 123456789012345678', () => {
    assert.strictEqual(parseEthToWei('0.123456789012345678'), '123456789012345678');
  });

  test('leading/trailing spaces stripped', () => {
    assert.strictEqual(parseEthToWei('  1  '), '1000000000000000000');
  });
});

describe('parseEthToWei — invalid inputs (must throw)', () => {
  const invalid = [
    ['zero', '0'],
    ['negative', '-1'],
    ['scientific', '1e3'],
    ['trailing dot', '1.'],
    ['leading dot', '.5'],
    ['alpha', 'abc'],
    ['more than 18 decimals', '0.1234567890123456789'],
    ['empty string', ''],
    ['null-ish', null],
    ['two dots', '1.2.3'],
  ];

  for (const [label, val] of invalid) {
    test(`rejects ${label}: ${JSON.stringify(val)}`, () => {
      assert.throws(() => parseEthToWei(val), Error);
    });
  }
});

// ─── weiToEthString ───────────────────────────────────────────────────────────

describe('weiToEthString', () => {
  test('1000000000000000000 → "1"', () => {
    assert.strictEqual(weiToEthString('1000000000000000000'), '1');
  });

  test('1 → "0.000000000000000001"', () => {
    assert.strictEqual(weiToEthString('1'), '0.000000000000000001');
  });

  test('500000000000000000 → "0.5"', () => {
    assert.strictEqual(weiToEthString('500000000000000000'), '0.5');
  });

  test('0 → "0"', () => {
    assert.strictEqual(weiToEthString('0'), '0');
  });

  test('round-trip: parseEthToWei then weiToEthString', () => {
    const eth = '0.123456789012345678';
    assert.strictEqual(weiToEthString(parseEthToWei(eth)), eth);
  });
});

// ─── isValidWeiString ─────────────────────────────────────────────────────────

describe('isValidWeiString', () => {
  test('"0" is valid', () => assert.ok(isValidWeiString('0')));
  test('"1" is valid', () => assert.ok(isValidWeiString('1')));
  test('"1000000000000000000" is valid', () => assert.ok(isValidWeiString('1000000000000000000')));
  test('"01" is invalid (leading zero)', () => assert.ok(!isValidWeiString('01')));
  test('"-1" is invalid', () => assert.ok(!isValidWeiString('-1')));
  test('"1.0" is invalid (decimal)', () => assert.ok(!isValidWeiString('1.0')));
  test('"1e3" is invalid', () => assert.ok(!isValidWeiString('1e3')));
  test('empty string is invalid', () => assert.ok(!isValidWeiString('')));
  test('number 1 is invalid (wrong type)', () => assert.ok(!isValidWeiString(1)));
});

// ─── compareWei ───────────────────────────────────────────────────────────────

describe('compareWei', () => {
  test('a < b → -1', () => assert.strictEqual(compareWei('0', '1'), -1));
  test('a > b → 1',  () => assert.strictEqual(compareWei('2', '1'), 1));
  test('a === b → 0', () => assert.strictEqual(compareWei('1000', '1000'), 0));
  test('large values', () => {
    assert.strictEqual(compareWei('1000000000000000000', '999999999999999999'), 1);
  });
});

// ─── buildSubmitBody ──────────────────────────────────────────────────────────

describe('buildSubmitBody', () => {
  test('produces valid JSON with integer value_wei', () => {
    const body = buildSubmitBody({
      walletAddress: '0xabc',
      target: '0xdef',
      valueWei: '123456789012345678',
      data: '0x',
      signature: 'sig==',
    });
    const parsed = JSON.parse(body);
    assert.strictEqual(parsed.wallet_address, '0xabc');
    assert.strictEqual(parsed.target, '0xdef');
    assert.strictEqual(parsed.data, '0x');
    assert.strictEqual(parsed.ml_dsa_signature, 'sig==');
    // value_wei parsed as a number by JSON.parse — just verify the body string
    // contains the digits without quotes
    assert.ok(body.includes(',"value_wei":123456789012345678,'));
  });

  test('throws on invalid wei string', () => {
    assert.throws(() => buildSubmitBody({
      walletAddress: '0x', target: '0x', valueWei: '1.5', data: '0x', signature: 'x',
    }));
  });

  test('throws on leading zero wei', () => {
    assert.throws(() => buildSubmitBody({
      walletAddress: '0x', target: '0x', valueWei: '01', data: '0x', signature: 'x',
    }));
  });
});
