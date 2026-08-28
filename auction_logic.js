(function (root, factory) {
  'use strict';

  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.TransferbrettAuction = api;
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function fail(code, message) {
    var error = new Error(message || code);
    error.code = code;
    throw error;
  }

  function clone(value) {
    if (typeof structuredClone === 'function') return structuredClone(value);
    return JSON.parse(JSON.stringify(value));
  }

  function isFiniteNumber(value) {
    return typeof value === 'number' && isFinite(value);
  }

  function money(value) {
    return Math.round((value + Number.EPSILON) * 1000000) / 1000000;
  }

  function sameMoney(left, right) {
    if (left === null || right === null) return left === right;
    return isFiniteNumber(left) && isFiniteNumber(right) && money(left) === money(right);
  }

  function isVisibleTenth(value) {
    return isFiniteNumber(value) && Math.abs(value * 10 - Math.round(value * 10)) < 0.000001;
  }

  function requireAdmin(state, actorToken) {
    if (typeof state.adminToken !== 'string' || !state.adminToken || actorToken !== state.adminToken) {
      fail('UNAUTHORIZED_ADMIN');
    }
  }

  function requireState(state) {
    if (!state || typeof state !== 'object' || Array.isArray(state)) fail('INVALID_STATE');
    if (!Array.isArray(state.teams)) fail('INVALID_STATE', 'teams must be an array');
    if (!state.presence || typeof state.presence !== 'object' || Array.isArray(state.presence)) {
      fail('INVALID_STATE', 'presence must be an object');
    }
  }

  function requireActiveSession(state) {
    if (!state.auction || state.auction.active !== true) fail('SESSION_INACTIVE');
    return state.auction;
  }

  function participantByToken(auction, token) {
    return auction.participants.filter(function (participant) {
      return participant.token === token;
    })[0] || null;
  }

  function teamById(state, teamId) {
    return state.teams.filter(function (team) { return team.id === teamId; })[0] || null;
  }

  function nextHistoryId(history) {
    return history.reduce(function (highest, entry) {
      return Math.max(highest, isFiniteNumber(entry && entry.id) ? entry.id : 0);
    }, 0) + 1;
  }

  function startSession(state, options) {
    requireState(state);
    options = options || {};
    requireAdmin(state, options.actorToken);
    if (state.auction && state.auction.active === true) fail('SESSION_ALREADY_ACTIVE');
    if (!isVisibleTenth(options.bidIncrement) || options.bidIncrement <= 0 || options.bidIncrement > 1000000) fail('INVALID_BID_INCREMENT');

    var validTeamIds = {};
    state.teams.forEach(function (team) {
      if (team && typeof team.id === 'string') validTeamIds[team.id] = true;
    });
    var participants = Object.keys(state.presence).reduce(function (result, token) {
      var presence = state.presence[token];
      if (presence && validTeamIds[presence.teamId]) {
        result.push({ token: token, name: presence.name, teamId: presence.teamId });
      }
      return result;
    }, []);
    if (participants.length === 0) fail('NO_ELIGIBLE_PARTICIPANTS');

    var turnIndex = participants.findIndex(function (participant) {
      return participant.token === options.startNominatorToken;
    });
    if (turnIndex < 0) fail('INVALID_START_NOMINATOR');

    var next = clone(state);
    next.auction = {
      active: true,
      startedAt: options.now,
      endedAt: null,
      participants: participants,
      turnIndex: turnIndex,
      currentNominatorToken: participants[turnIndex].token,
      bidIncrement: money(options.bidIncrement),
      lot: null,
      usedLotIds: [],
    };
    return next;
  }

  function nominatePlayer(state, options) {
    requireState(state);
    options = options || {};
    var auction = requireActiveSession(state);
    if (auction.lot) fail('LOT_ALREADY_ACTIVE');
    if (options.token !== auction.currentNominatorToken) fail('NOT_CURRENT_NOMINATOR');
    if (!participantByToken(auction, options.token)) fail('TEAM_NOT_PARTICIPANT');
    if (!options.player || typeof options.player.id !== 'string' || !options.player.id) fail('INVALID_PLAYER');
    if (!isVisibleTenth(options.startPrice) || options.startPrice < 0 || options.startPrice > 1000000) fail('INVALID_START_PRICE');
    if (typeof options.lotId !== 'string' || !options.lotId) fail('INVALID_LOT_ID');
    if ((auction.usedLotIds || []).indexOf(options.lotId) !== -1) fail('DUPLICATE_LOT_ID');
    if (state.purchases && state.purchases[options.player.id]) fail('PLAYER_ALREADY_SOLD');

    var playerName = options.player.name || options.player.n;
    if (typeof playerName !== 'string' || !playerName) fail('INVALID_PLAYER');

    var next = clone(state);
    if (!Array.isArray(next.auction.usedLotIds)) next.auction.usedLotIds = [];
    next.auction.usedLotIds.push(options.lotId);
    next.auction.lot = {
      id: options.lotId,
      playerId: options.player.id,
      playerName: playerName,
      startPrice: money(options.startPrice),
      highestBid: null,
      highestTeamId: null,
      bidCount: 0,
      nominatedByToken: options.token,
      nominatedAt: options.now,
    };
    return next;
  }

  function placeBid(state, options) {
    requireState(state);
    options = options || {};
    var auction = requireActiveSession(state);
    if (!auction.lot) fail('NO_ACTIVE_LOT');

    var participant = participantByToken(auction, options.token);
    if (!participant) fail('TEAM_NOT_PARTICIPANT');
    if (participant.teamId !== options.teamId) fail('PARTICIPANT_TEAM_MISMATCH');
    var team = teamById(state, options.teamId);
    if (!team) fail('TEAM_NOT_PARTICIPANT');
    if (auction.lot.highestTeamId === options.teamId) fail('TEAM_ALREADY_LEADING');

    if (!sameMoney(options.expectedCurrentBid, auction.lot.highestBid)) fail('STALE_BID');
    if (!isVisibleTenth(options.amount)) fail('INVALID_BID_INCREMENT');
    var requiredBid = auction.lot.highestBid === null
      ? auction.lot.startPrice
      : money(auction.lot.highestBid + auction.bidIncrement);
    if (money(options.amount) < money(requiredBid)) fail('INVALID_BID_INCREMENT');
    if (!isFiniteNumber(team.balance) || money(options.amount) > money(team.balance)) {
      fail('INSUFFICIENT_BUDGET');
    }

    var next = clone(state);
    next.auction.lot.highestBid = money(options.amount);
    next.auction.lot.highestTeamId = options.teamId;
    next.auction.lot.highestBidderToken = options.token;
    next.auction.lot.highestBidAt = options.now;
    next.auction.lot.bidCount = (next.auction.lot.bidCount || 0) + 1;
    return next;
  }

  function requireCurrentLot(state, expectedLotId) {
    var auction = requireActiveSession(state);
    if (!auction.lot) fail('NO_ACTIVE_LOT');
    if (auction.lot.id !== expectedLotId) fail('STALE_LOT');
    return auction;
  }

  function finalizeLot(state, options) {
    requireState(state);
    options = options || {};
    requireAdmin(state, options.actorToken);
    var auction = requireCurrentLot(state, options.expectedLotId);
    var lot = auction.lot;
    if (lot.highestBid === null || !lot.highestTeamId) fail('NO_WINNING_BID');
    if (state.purchases && state.purchases[lot.playerId]) fail('PLAYER_ALREADY_SOLD');

    var winner = teamById(state, lot.highestTeamId);
    if (!winner) fail('TEAM_NOT_PARTICIPANT');
    if (!isFiniteNumber(winner.balance) || money(lot.highestBid) > money(winner.balance)) {
      fail('INSUFFICIENT_BUDGET');
    }

    var next = clone(state);
    if (!next.purchases || typeof next.purchases !== 'object' || Array.isArray(next.purchases)) {
      next.purchases = {};
    }
    if (!Array.isArray(next.history)) next.history = [];
    var nextWinner = teamById(next, lot.highestTeamId);
    nextWinner.balance = money(nextWinner.balance - lot.highestBid);
    next.purchases[lot.playerId] = { teamId: lot.highestTeamId, price: money(lot.highestBid) };
    next.history.push({
      id: nextHistoryId(next.history),
      playerId: lot.playerId,
      playerName: lot.playerName,
      teamId: lot.highestTeamId,
      teamName: nextWinner.name || '?',
      price: money(lot.highestBid),
      fromTeamId: null,
      fromTeamName: null,
      ts: options.now,
      undone: false,
      source: 'auction',
      lotId: lot.id,
    });
    next.auction.lot = null;
    // If the person who nominated this lot left meanwhile, leaveSession already handed the turn
    // to the correct successor. Rotating again here would skip that person.
    if (participantByToken(next.auction, lot.nominatedByToken)) {
      next.auction.turnIndex = (next.auction.turnIndex + 1) % next.auction.participants.length;
      next.auction.currentNominatorToken = next.auction.participants[next.auction.turnIndex].token;
    }
    return next;
  }

  function cancelLot(state, options) {
    requireState(state);
    options = options || {};
    requireAdmin(state, options.actorToken);
    requireCurrentLot(state, options.expectedLotId);
    var next = clone(state);
    next.auction.lot = null;
    next.auction.lastCanceledAt = options.now;
    return next;
  }

  function skipNominator(state, options) {
    requireState(state);
    options = options || {};
    requireAdmin(state, options.actorToken);
    var auction = requireActiveSession(state);
    if (auction.lot) fail('LOT_ALREADY_ACTIVE');
    var next = clone(state);
    next.auction.turnIndex = (next.auction.turnIndex + 1) % next.auction.participants.length;
    next.auction.currentNominatorToken = next.auction.participants[next.auction.turnIndex].token;
    next.auction.lastSkippedAt = options.now;
    return next;
  }

  function endSession(state, options) {
    requireState(state);
    options = options || {};
    requireAdmin(state, options.actorToken);
    var auction = requireActiveSession(state);
    if (auction.lot) fail('LOT_ALREADY_ACTIVE');
    var next = clone(state);
    next.auction.active = false;
    next.auction.endedAt = options.now;
    return next;
  }

  function leaveSession(state, options) {
    requireState(state);
    options = options || {};
    var auction = requireActiveSession(state);
    if (typeof options.token !== 'string' || !options.token) fail('TEAM_NOT_PARTICIPANT');

    var leavingIndex = auction.participants.findIndex(function (participant) {
      return participant.token === options.token;
    });
    var departingAdmin = state.adminToken === options.token;
    // A second attempt after a partial network failure may find the participant already removed
    // while its presence record is still visible. Treat that retry as idempotent.
    if (leavingIndex < 0 && !departingAdmin && !state.presence[options.token]) fail('TEAM_NOT_PARTICIPANT');

    var next = clone(state);
    if (leavingIndex >= 0) {
      var oldCurrentToken = auction.currentNominatorToken;
      var successorToken = auction.participants[(leavingIndex + 1) % auction.participants.length].token;
      next.auction.participants.splice(leavingIndex, 1);

      if (next.auction.participants.length === 0) {
        next.auction.active = false;
        next.auction.endedAt = options.now;
        next.auction.lot = null;
        next.auction.turnIndex = 0;
        next.auction.currentNominatorToken = null;
      } else {
        var desiredCurrentToken = oldCurrentToken === options.token ? successorToken : oldCurrentToken;
        var desiredIndex = next.auction.participants.findIndex(function (participant) {
          return participant.token === desiredCurrentToken;
        });
        if (desiredIndex < 0) desiredIndex = 0;
        next.auction.turnIndex = desiredIndex;
        next.auction.currentNominatorToken = next.auction.participants[desiredIndex].token;
      }
    }

    if (departingAdmin) {
      next.adminToken = next.auction.active && next.auction.currentNominatorToken
        ? next.auction.currentNominatorToken
        : null;
    }
    next.auction.lastLeftAt = options.now;
    return next;
  }

  return {
    startSession: startSession,
    nominatePlayer: nominatePlayer,
    placeBid: placeBid,
    finalizeLot: finalizeLot,
    cancelLot: cancelLot,
    skipNominator: skipNominator,
    endSession: endSession,
    leaveSession: leaveSession,
  };
}));
