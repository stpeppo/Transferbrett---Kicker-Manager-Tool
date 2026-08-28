'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  startSession,
  nominatePlayer,
  placeBid,
  finalizeLot,
  cancelLot,
  skipNominator,
  endSession,
} = require('../auction_logic');

function baseState(overrides = {}) {
  return {
    teams: [
      { id: 'team-a', name: 'Alpha', budget: 80, balance: 80 },
      { id: 'team-b', name: 'Bravo', budget: 90, balance: 90 },
      { id: 'team-c', name: 'Charlie', budget: 70, balance: 70 },
    ],
    presence: {
      alice: { name: 'Alice', teamId: 'team-a', lastSeen: 1_000 },
      bob: { name: 'Bob', teamId: 'team-b', lastSeen: 1_001 },
      spectator: { name: 'Spec', teamId: null, lastSeen: 1_002 },
      orphan: { name: 'Orphan', teamId: 'missing-team', lastSeen: 1_003 },
    },
    purchases: {},
    history: [],
    adminToken: 'admin-token',
    auction: null,
    ...overrides,
  };
}

function activeSession() {
  return startSession(baseState(), {
    actorToken: 'admin-token',
    startBudget: 125,
    startNominatorToken: 'alice',
    bidIncrement: 0.5,
    now: 2_000,
  });
}

function activeLot() {
  return nominatePlayer(activeSession(), {
    token: 'alice',
    player: { id: 'player-7', name: 'Test Spieler', value: 10 },
    startPrice: 10,
    lotId: 'lot-1',
    now: 2_100,
  });
}

function expectCode(code, operation) {
  assert.throws(operation, (error) => error && error.code === code);
}

test('session start snapshots only present browsers with a valid team and applies the chosen common budget', () => {
  const before = baseState();
  const next = startSession(before, {
    actorToken: 'admin-token',
    startBudget: 125,
    startNominatorToken: 'alice',
    bidIncrement: 0.5,
    now: 2_000,
  });

  assert.deepEqual(next.auction.participants, [
    { token: 'alice', name: 'Alice', teamId: 'team-a' },
    { token: 'bob', name: 'Bob', teamId: 'team-b' },
  ]);
  assert.equal(next.auction.currentNominatorToken, 'alice');
  assert.equal(next.auction.bidIncrement, 0.5);
  assert.equal(next.auction.active, true);
  assert.deepEqual(
    next.teams.map(({ id, budget, balance }) => ({ id, budget, balance })),
    [
      { id: 'team-a', budget: 125, balance: 125 },
      { id: 'team-b', budget: 125, balance: 125 },
      { id: 'team-c', budget: 70, balance: 70 },
    ],
  );
  assert.equal(before.teams[0].budget, 80, 'transition must not mutate its input snapshot');
});

test('session start never resets budgets once purchases already exist', () => {
  const before = baseState({
    purchases: { existing: { teamId: 'team-a', price: 20 } },
    teams: [
      { id: 'team-a', name: 'Alpha', budget: 80, balance: 60 },
      { id: 'team-b', name: 'Bravo', budget: 90, balance: 90 },
    ],
  });

  const next = startSession(before, {
    actorToken: 'admin-token',
    startBudget: 125,
    startNominatorToken: 'alice',
    bidIncrement: 0.5,
    now: 2_000,
  });

  assert.deepEqual(next.teams, before.teams);
});

test('only the snapshotted current nominator can place an unsold player on the lot', () => {
  const session = activeSession();
  const nomination = {
    player: { id: 'player-7', name: 'Test Spieler', value: 10 },
    startPrice: 10,
    lotId: 'lot-1',
    now: 2_100,
  };

  expectCode('NOT_CURRENT_NOMINATOR', () =>
    nominatePlayer(session, { ...nomination, token: 'bob' }),
  );

  const next = nominatePlayer(session, { ...nomination, token: 'alice' });
  assert.deepEqual(next.auction.lot, {
    id: 'lot-1',
    playerId: 'player-7',
    playerName: 'Test Spieler',
    startPrice: 10,
    highestBid: null,
    highestTeamId: null,
    bidCount: 0,
    nominatedByToken: 'alice',
    nominatedAt: 2_100,
  });
});

test('valid bids use exactly the fixed increment and retain the winning browser and team', () => {
  let state = placeBid(activeLot(), {
    token: 'bob',
    teamId: 'team-b',
    amount: 10,
    expectedCurrentBid: null,
    now: 2_200,
  });
  assert.equal(state.auction.lot.highestBid, 10);
  assert.equal(state.auction.lot.highestTeamId, 'team-b');
  assert.equal(state.auction.lot.highestBidderToken, 'bob');
  assert.equal(state.auction.lot.bidCount, 1);

  state = placeBid(state, {
    token: 'alice',
    teamId: 'team-a',
    amount: 10.5,
    expectedCurrentBid: 10,
    now: 2_201,
  });
  assert.equal(state.auction.lot.highestBid, 10.5);
  assert.equal(state.auction.lot.highestTeamId, 'team-a');
  assert.equal(state.auction.lot.bidCount, 2);
});

test('bids reject stale/equal amounts so simultaneous bidders cannot overwrite a newer bid', () => {
  const afterFirstBid = placeBid(activeLot(), {
    token: 'bob',
    teamId: 'team-b',
    amount: 10,
    expectedCurrentBid: null,
    now: 2_200,
  });

  expectCode('STALE_BID', () =>
    placeBid(afterFirstBid, {
      token: 'alice',
      teamId: 'team-a',
      amount: 10,
      expectedCurrentBid: null,
      now: 2_201,
    }),
  );
  expectCode('INVALID_BID_INCREMENT', () =>
    placeBid(afterFirstBid, {
      token: 'alice',
      teamId: 'team-a',
      amount: 10,
      expectedCurrentBid: 10,
      now: 2_201,
    }),
  );
});

test('the leading team cannot raise its own bid and increments use visible tenths of a million', () => {
  const afterFirstBid = placeBid(activeLot(), {
    token: 'bob', teamId: 'team-b', amount: 10, expectedCurrentBid: null,
  });
  expectCode('TEAM_ALREADY_LEADING', () =>
    placeBid(afterFirstBid, {
      token: 'bob', teamId: 'team-b', amount: 10.5, expectedCurrentBid: 10,
    }),
  );
  expectCode('INVALID_BID_INCREMENT', () =>
    startSession(baseState(), {
      actorToken: 'admin-token', startBudget: 100,
      startNominatorToken: 'alice', bidIncrement: 0.15,
    }),
  );
});

test('bids validate active session, participant/team ownership, and remaining budget', () => {
  expectCode('SESSION_INACTIVE', () =>
    placeBid(baseState(), {
      token: 'alice', teamId: 'team-a', amount: 10, expectedCurrentBid: null,
    }),
  );
  expectCode('TEAM_NOT_PARTICIPANT', () =>
    placeBid(activeLot(), {
      token: 'spectator', teamId: 'team-c', amount: 10, expectedCurrentBid: null,
    }),
  );
  expectCode('PARTICIPANT_TEAM_MISMATCH', () =>
    placeBid(activeLot(), {
      token: 'alice', teamId: 'team-b', amount: 10, expectedCurrentBid: null,
    }),
  );

  const expensiveLot = nominatePlayer(activeSession(), {
    token: 'alice',
    player: { id: 'player-99', name: 'Zu teuer', value: 130 },
    startPrice: 130,
    lotId: 'lot-expensive',
    now: 2_100,
  });
  expectCode('INSUFFICIENT_BUDGET', () =>
    placeBid(expensiveLot, {
      token: 'bob', teamId: 'team-b', amount: 130, expectedCurrentBid: null,
    }),
  );
});

test('finalize creates one purchase/history entry, debits once, and rotates the nominator atomically', () => {
  const withBid = placeBid(activeLot(), {
    token: 'bob',
    teamId: 'team-b',
    amount: 10,
    expectedCurrentBid: null,
    now: 2_200,
  });
  const finalized = finalizeLot(withBid, {
    actorToken: 'admin-token',
    expectedLotId: 'lot-1',
    now: 2_300,
  });

  assert.deepEqual(finalized.purchases['player-7'], { teamId: 'team-b', price: 10 });
  assert.equal(finalized.teams.find((team) => team.id === 'team-b').balance, 115);
  assert.equal(finalized.history.length, 1);
  assert.deepEqual(
    {
      playerId: finalized.history[0].playerId,
      playerName: finalized.history[0].playerName,
      teamId: finalized.history[0].teamId,
      teamName: finalized.history[0].teamName,
      price: finalized.history[0].price,
      source: finalized.history[0].source,
    },
    {
      playerId: 'player-7',
      playerName: 'Test Spieler',
      teamId: 'team-b',
      teamName: 'Bravo',
      price: 10,
      source: 'auction',
    },
  );
  assert.equal(finalized.auction.lot, null);
  assert.equal(finalized.auction.currentNominatorToken, 'bob');

  expectCode('NO_ACTIVE_LOT', () =>
    finalizeLot(finalized, { actorToken: 'admin-token', expectedLotId: 'lot-1', now: 2_301 }),
  );
  assert.equal(finalized.teams.find((team) => team.id === 'team-b').balance, 115);
  assert.equal(finalized.history.length, 1);
});

test('canceling a lot preserves every balance and lets the same nominator choose again', () => {
  const withBid = placeBid(activeLot(), {
    token: 'bob',
    teamId: 'team-b',
    amount: 10,
    expectedCurrentBid: null,
    now: 2_200,
  });
  const balances = withBid.teams.map(({ id, balance }) => ({ id, balance }));

  const canceled = cancelLot(withBid, { actorToken: 'admin-token', expectedLotId: 'lot-1', now: 2_300 });

  assert.deepEqual(canceled.teams.map(({ id, balance }) => ({ id, balance })), balances);
  assert.equal(canceled.auction.currentNominatorToken, 'alice');
  assert.equal(canceled.auction.lot, null);
  assert.deepEqual(canceled.purchases, {});
  assert.deepEqual(canceled.history, []);

  const nominatedAgain = nominatePlayer(canceled, {
    token: 'alice',
    player: { id: 'player-8', name: 'Naechster Spieler', value: 8 },
    startPrice: 8,
    lotId: 'lot-2',
    now: 2_400,
  });
  assert.equal(nominatedAgain.auction.lot.playerId, 'player-8');
});

test('skipping without an active lot rotates the nomination right to the next person', () => {
  const skipped = skipNominator(activeSession(), { actorToken: 'admin-token', now: 2_250 });

  assert.equal(skipped.auction.currentNominatorToken, 'bob');
  assert.equal(skipped.auction.turnIndex, 1);
  assert.equal(skipped.auction.lastSkippedAt, 2_250);
  expectCode('LOT_ALREADY_ACTIVE', () => skipNominator(activeLot(), { actorToken: 'admin-token', now: 2_251 }));
});

test('ending a session records its end and prevents further nominations or bids', () => {
  const ended = endSession(activeSession(), { actorToken: 'admin-token', now: 3_000 });

  assert.equal(ended.auction.active, false);
  assert.equal(ended.auction.endedAt, 3_000);
  expectCode('SESSION_INACTIVE', () =>
    nominatePlayer(ended, {
      token: 'alice',
      player: { id: 'player-8', name: 'Zu spaet', value: 8 },
      startPrice: 8,
      lotId: 'lot-late',
    }),
  );
});

test('admin transitions reject every browser token except the current admin token', () => {
  expectCode('UNAUTHORIZED_ADMIN', () => startSession(baseState(), {
    actorToken: 'alice', startBudget: 100, startNominatorToken: 'alice', bidIncrement: 0.5,
  }));
  expectCode('UNAUTHORIZED_ADMIN', () => finalizeLot(activeLot(), {
    actorToken: 'alice', expectedLotId: 'lot-1',
  }));
  expectCode('UNAUTHORIZED_ADMIN', () => cancelLot(activeLot(), {
    actorToken: 'alice', expectedLotId: 'lot-1',
  }));
  expectCode('UNAUTHORIZED_ADMIN', () => skipNominator(activeSession(), { actorToken: 'alice' }));
  expectCode('UNAUTHORIZED_ADMIN', () => endSession(activeSession(), { actorToken: 'alice' }));
});

test('session start rejects an existing session and invalid configuration', () => {
  expectCode('SESSION_ALREADY_ACTIVE', () =>
    startSession(activeSession(), {
      actorToken: 'admin-token', startBudget: 100, startNominatorToken: 'alice', bidIncrement: 0.5,
    }),
  );
  expectCode('INVALID_START_BUDGET', () =>
    startSession(baseState(), {
      actorToken: 'admin-token', startBudget: -1, startNominatorToken: 'alice', bidIncrement: 0.5,
    }),
  );
  expectCode('INVALID_BID_INCREMENT', () =>
    startSession(baseState(), {
      actorToken: 'admin-token', startBudget: 100, startNominatorToken: 'alice', bidIncrement: 0,
    }),
  );
  expectCode('INVALID_START_NOMINATOR', () =>
    startSession(baseState(), {
      actorToken: 'admin-token', startBudget: 100, startNominatorToken: 'spectator', bidIncrement: 0.5,
    }),
  );
  expectCode('NO_ELIGIBLE_PARTICIPANTS', () =>
    startSession(baseState({ presence: {} }), {
      actorToken: 'admin-token', startBudget: 100, startNominatorToken: 'alice', bidIncrement: 0.5,
    }),
  );
});

test('nomination rejects an occupied lot, sold players, and reused lot IDs', () => {
  expectCode('LOT_ALREADY_ACTIVE', () =>
    nominatePlayer(activeLot(), {
      token: 'alice',
      player: { id: 'player-8', name: 'Zweiter Spieler' },
      startPrice: 8,
      lotId: 'lot-2',
    }),
  );

  const soldState = activeSession();
  soldState.purchases['player-7'] = { teamId: 'team-b', price: 10 };
  expectCode('PLAYER_ALREADY_SOLD', () =>
    nominatePlayer(soldState, {
      token: 'alice',
      player: { id: 'player-7', name: 'Test Spieler' },
      startPrice: 10,
      lotId: 'lot-sold',
    }),
  );

  const canceled = cancelLot(activeLot(), { actorToken: 'admin-token', expectedLotId: 'lot-1', now: 2_300 });
  expectCode('DUPLICATE_LOT_ID', () =>
    nominatePlayer(canceled, {
      token: 'alice',
      player: { id: 'player-8', name: 'Zweiter Spieler' },
      startPrice: 8,
      lotId: 'lot-1',
    }),
  );
});

test('lot completion rejects stale lot snapshots and a lot without a winning bid', () => {
  expectCode('STALE_LOT', () =>
    finalizeLot(activeLot(), { actorToken: 'admin-token', expectedLotId: 'lot-stale', now: 2_300 }),
  );
  expectCode('STALE_LOT', () =>
    cancelLot(activeLot(), { actorToken: 'admin-token', expectedLotId: 'lot-stale', now: 2_300 }),
  );
  expectCode('NO_WINNING_BID', () =>
    finalizeLot(activeLot(), { actorToken: 'admin-token', expectedLotId: 'lot-1', now: 2_300 }),
  );
  expectCode('LOT_ALREADY_ACTIVE', () =>
    endSession(activeLot(), { actorToken: 'admin-token', now: 3_000 }),
  );
});

test('domain transitions reject malformed state and tolerate omitted option objects safely', () => {
  expectCode('INVALID_STATE', () => startSession(null));
  expectCode('INVALID_STATE', () => startSession({ presence: {}, teams: null }));
  expectCode('INVALID_STATE', () => startSession({ teams: [], presence: null }));
  expectCode('UNAUTHORIZED_ADMIN', () => startSession(baseState()));
  expectCode('NOT_CURRENT_NOMINATOR', () => nominatePlayer(activeSession()));
  expectCode('TEAM_NOT_PARTICIPANT', () => placeBid(activeLot()));
  expectCode('UNAUTHORIZED_ADMIN', () => finalizeLot(activeLot()));
  expectCode('UNAUTHORIZED_ADMIN', () => cancelLot(activeLot()));

  const ended = endSession(activeSession(), { actorToken: 'admin-token' });
  assert.equal(ended.auction.active, false);
  assert.equal(ended.auction.endedAt, undefined);
});

test('player aliases and late concurrent state changes are validated at the transaction boundary', () => {
  const withAlias = nominatePlayer(activeSession(), {
    token: 'alice',
    player: { id: 'player-alias', n: 'Alias Name' },
    startPrice: 5,
    lotId: 'lot-alias',
  });
  assert.equal(withAlias.auction.lot.playerName, 'Alias Name');

  const missingTeam = activeLot();
  missingTeam.teams = missingTeam.teams.filter((team) => team.id !== 'team-b');
  expectCode('TEAM_NOT_PARTICIPANT', () =>
    placeBid(missingTeam, {
      token: 'bob', teamId: 'team-b', amount: 10, expectedCurrentBid: null,
    }),
  );

  const withBid = placeBid(activeLot(), {
    token: 'bob', teamId: 'team-b', amount: 10, expectedCurrentBid: null,
  });
  withBid.teams.find((team) => team.id === 'team-b').balance = 5;
  expectCode('INSUFFICIENT_BUDGET', () =>
    finalizeLot(withBid, { actorToken: 'admin-token', expectedLotId: 'lot-1' }),
  );
  withBid.teams.find((team) => team.id === 'team-b').balance = 125;
  withBid.purchases['player-7'] = { teamId: 'team-a', price: 9 };
  expectCode('PLAYER_ALREADY_SOLD', () =>
    finalizeLot(withBid, { actorToken: 'admin-token', expectedLotId: 'lot-1' }),
  );
});
