'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');

function read(name) {
  return fs.readFileSync(path.join(root, name), 'utf8');
}

test('template exposes the live auction panel and its primary controls', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /id="auctionPanel"/);
  assert.match(template, /id="startAuctionBtn"/);
  assert.match(template, /id="resumeAuctionBtn"/);
  assert.match(template, /id="auctionDropZone"/);
  assert.match(template, /id="auctionBidBtn"/);
  assert.match(template, /id="auctionBidAmount"/);
  assert.match(template, /Aktuelles Mindestgebot/);
});

test('a finished auction exposes an admin-only resume action', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /function resumeAuctionSession\(/);
  assert.match(template, /runAuctionTransition\('resumeSession'/);
  assert.match(template, /Auktion fortsetzen/);
  assert.match(template, /Neue Auktion starten/);
});

test('auction UI shows animated current bid and the complete bid history', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /Aktuelles Höchstgebot/);
  assert.match(template, /Gebotsverlauf/);
  assert.match(template, /lot\.bids/);
  assert.match(template, /@keyframes bidPop/);
  assert.match(template, /prefers-reduced-motion:reduce/);
});

test('auction panel is positioned directly between teams and the player table', () => {
  const template = read('transferbrett_template.html');
  const teamsIndex = template.indexOf('id="teamsGrid"');
  const auctionIndex = template.indexOf('id="auctionPanel"');
  const tableIndex = template.indexOf('id="tableWrap"');

  assert.ok(teamsIndex < auctionIndex);
  assert.ok(auctionIndex < tableIndex);
});

test('player search and filters sit between the auction and player table', () => {
  const template = read('transferbrett_template.html');
  const auctionIndex = template.indexOf('id="auctionPanel"');
  const controlsIndex = template.indexOf('id="playerControls"');
  const tableIndex = template.indexOf('id="tableWrap"');

  assert.ok(auctionIndex < controlsIndex);
  assert.ok(controlsIndex < tableIndex);
});

test('auction writes are connectivity-gated and use transactional state updates', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /ref\('\.info\/connected'\)/);
  assert.match(template, /stateRef\.transaction\(/);
  assert.match(template, /actorToken:\s*myToken/);
  assert.doesNotMatch(template, /stateRef\.set\(coreStateForSync\(\)\)/);
});

test('admin takeover remains available and transactional during a live auction', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /function changeAdmin\(nextToken\)/);
  assert.match(template, /changeAdmin\(myToken\)/);
  assert.match(template, /next\.adminToken = nextToken \|\| null/);
  assert.doesNotMatch(template, /adminBtn\.disabled = normalChangesLocked\(\)/);
});

test('the admin can assign teams to every present browser before the auction', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /function setPresenceTeam\(/);
  assert.match(template, /e\.tok===myToken \|\| isAdmin\(\)/);
  assert.match(template, /presenceRef\.child\(token\)\.update\(\{teamId:/);
});

test('local cached state is isolated by board code', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /var LS_KEY = 'transferbrett_state_v3:' \+ BOARD_ID/);
  assert.ok(template.indexOf('var BOARD_ID = getBoardId()') < template.indexOf('localStorage.getItem(LS_KEY)'));
  assert.doesNotMatch(template, /var LS_KEY = 'transferbrett_state_v2'/);
});

test('present browsers can explicitly leave the game', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /function leaveGame\(/);
  assert.match(template, /Spiel verlassen/);
  assert.match(template, /TransferbrettAuction\.leaveSession/);
  assert.match(template, /presenceRef\.child\(myToken\)\.remove\(\)/);
});

test('every player row exposes a turn-gated auction nomination button', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /nominateBtn\.textContent='Zur Auktion hinzufügen'/);
  assert.match(template, /!isCurrentNominator/);
  assert.match(template, /Du bist aktuell nicht mit der Nominierung dran/);
});

test('auction start keeps individual budgets and includes every assigned browser', () => {
  const template = read('transferbrett_template.html');

  assert.doesNotMatch(template, /id='auctionStartBudget'/);
  assert.doesNotMatch(template, /15\*60\*1000/);
  assert.match(template, /individuellen Budgets und aktuellen Kontostände/);
});

test('auction start fixes the complete participant order by explicit selection', () => {
  const template = read('transferbrett_template.html');

  assert.match(template, /Nominierungsreihenfolge/);
  assert.match(template, /participantOrderTokens/);
  assert.match(template, /Reihenfolge zufällig mischen/);
  assert.match(template, /Die Teilnehmerliste hat sich geändert/);
  assert.doesNotMatch(template, /auctionStartNominator/);
});

test('build script inlines the reusable auction domain logic', () => {
  const buildScript = read('build_transferbrett.py');

  assert.match(buildScript, /auction_logic\.js/);
  assert.match(buildScript, /__AUCTION_LOGIC__/);
});

test('generated standalone HTML contains auction logic without unresolved placeholders', () => {
  const built = read('transferbrett.html');

  assert.match(built, /TransferbrettAuction/);
  assert.match(built, /id="auctionPanel"/);
  assert.doesNotMatch(built, /__AUCTION_LOGIC__/);
});

test('every inline JavaScript block in the standalone build parses successfully', () => {
  const built = read('transferbrett.html');
  const scriptPattern = /<script([^>]*)>([\s\S]*?)<\/script>/g;
  let match;
  let parsed = 0;

  while ((match = scriptPattern.exec(built)) !== null) {
    if (/type="application\/json"/.test(match[1]) || !match[2].trim()) continue;
    assert.doesNotThrow(() => new vm.Script(match[2]));
    parsed += 1;
  }

  assert.ok(parsed >= 2, 'expected auction logic and application script blocks');
});
