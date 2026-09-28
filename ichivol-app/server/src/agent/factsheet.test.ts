/**
 * AG-FS0 — validateur de sortie + agent FactSheet (LLM simulé, sans réseau).
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  compactFacts,
  parseAnalysis,
  renderAnswer,
  runFactsheetAgent,
  SUBMIT_ANALYSIS_TOOL,
} from './factsheetAgent.js'
import {
  type AnalysisOutput,
  type Claim,
  type Fact,
  type FactSheet,
  extractNumbers,
  needsRetry,
  validateAnalysis,
} from './factsheetValidate.js'

function fact(id: string, value: unknown, display: string | null, over: Partial<Fact> = {}): Fact {
  return {
    id,
    engine: id.split('.')[0],
    field: id.split('.').slice(1).join('.'),
    value,
    display,
    timeframe: '1h',
    as_of: 1_790_596_800,
    known_at: 1_790_596_800,
    source: 'engine',
    status: value === null ? 'unavailable' : 'ok',
    validation_status: 'NON_VALIDE',
    decision_role: 'decision',
    ...over,
  }
}

const FS: FactSheet = {
  schema: 'ichivol.factsheet.v1',
  factsheet_id: 'abc123def456',
  symbol: 'BTCUSDT',
  timeframe: '1h',
  as_of: 1_790_596_800, // 2026-09-28 12:00 UTC
  facts: [
    fact('pipeline.decision', 'NO_TRADE', 'NO_TRADE'),
    fact('rvol.rvol', 1.5290476, '1,529'),
    fact('rvol.percentile', 0.93, '0,93'),
    fact('price.live', 83703.349, '83703,35', { source: 'provider' }),
    fact('atr.atr', 472.0964, '472,1'),
    fact('structure.last_swing_high', 83820, '83820'),
    fact('calendar.next_high.time_utc', '2026-09-29 04:30 UTC', '2026-09-29 04:30 UTC', { source: 'calendar' }),
    fact('cvd.delta', null, null, { reason: 'provider_no_taker_volume' }),
  ],
  missing: [{ id: 'cvd.delta', reason: 'provider_no_taker_volume' }],
}

function out(over: Partial<AnalysisOutput> = {}): AnalysisOutput {
  return {
    summary: 'Le pipeline ne trade pas (NO_TRADE, signal NON_VALIDE).',
    claims: [
      { text: 'Le RVOL est de 1,529, au 93e percentile.', kind: 'fact', fact_ids: ['rvol.rvol', 'rvol.percentile'] },
      { text: "L'ATR 14 vaut 472,1.", kind: 'fact', fact_ids: ['atr.atr'] },
    ],
    risks: [{ text: 'Prix à 83703,35 ; dernier sommet à 83820.', kind: 'fact', fact_ids: ['price.live', 'structure.last_swing_high'] }],
    invalidation: [],
    missing_data: [],
    ...over,
  }
}

describe('extractNumbers', () => {
  it('lit FR/EN, %, et ignore timeframes et périodes', () => {
    assert.deepEqual(extractNumbers('Signaux NON_VALIDE (VP3), étape AG-S1, stratégie B7.'), [])
    const n = extractNumbers('RVOL 1,529 (93 %) en 1h, ATR(14) = 472.1, prix 83 703,35, Donchian 55/20')
    assert.deepEqual(
      n.map((x) => [x.value, x.percent]),
      [
        [1.529, false],
        [93, true],
        [472.1, false],
        [83703.35, false],
      ],
    )
  })
})

describe('validateAnalysis', () => {
  it('accepte une réponse dont chaque chiffre vient d’un fait cité', () => {
    const r = validateAnalysis(FS, out())
    assert.equal(r.rejected, 0, JSON.stringify(r.verdicts.filter((v) => !v.ok)))
    assert.equal(r.summaryOk, true)
    assert.equal(needsRetry(r), false)
  })

  it('rejette un chiffre inventé', () => {
    const r = validateAnalysis(FS, out({ claims: [{ text: 'Le RSI est à 71.', kind: 'fact', fact_ids: ['rvol.rvol'] }] }))
    assert.equal(r.rejected, 1)
    assert.match(r.verdicts[0].errors.join(), /nombre non sourcé: 71/)
  })

  it('rejette un chiffre vrai mais non cité par le claim', () => {
    const r = validateAnalysis(FS, out({ claims: [{ text: "L'ATR vaut 472,1.", kind: 'fact', fact_ids: ['rvol.rvol'] }] }))
    assert.equal(r.verdicts.find((v) => v.section === 'claims')!.ok, false)
  })

  it('accepte arrondi et variantes de format', () => {
    for (const text of ['RVOL 1,53', 'RVOL 1.529', 'RVOL 1,529']) {
      const r = validateAnalysis(FS, out({ claims: [{ text, kind: 'fact', fact_ids: ['rvol.rvol'] }], risks: [] }))
      assert.equal(r.rejected, 0, text)
    }
    // V5 : précision insuffisante
    const r = validateAnalysis(FS, out({ claims: [{ text: 'RVOL environ 1,5', kind: 'fact', fact_ids: ['rvol.rvol'] }], risks: [] }))
    assert.equal(r.rejected, 1)
  })

  it('refuse un fait indisponible cité comme donnée, mais l’accepte en « missing »', () => {
    const asFact = validateAnalysis(FS, out({ claims: [{ text: 'Le CVD est acheteur.', kind: 'fact', fact_ids: ['cvd.delta'] }], risks: [] }))
    assert.equal(asFact.rejected, 1)
    const asMissing = validateAnalysis(FS, out({ claims: [{ text: 'Le delta CVD est indisponible.', kind: 'missing', fact_ids: ['cvd.delta'] }], risks: [] }))
    assert.equal(asMissing.rejected, 0)
  })

  it('refuse un id inconnu et un claim factuel sans fait', () => {
    const r = validateAnalysis(
      FS,
      out({
        claims: [
          { text: 'Tendance forte.', kind: 'fact', fact_ids: [] },
          { text: 'ADX élevé.', kind: 'fact', fact_ids: ['adx.adx'] },
        ],
        risks: [],
      }),
    )
    assert.equal(r.rejected, 2)
  })

  it('accepte heures et dates issues d’un fait cité', () => {
    const r = validateAnalysis(
      FS,
      out({ claims: [{ text: 'Événement macro le 2026-09-29 à 04:30 UTC.', kind: 'fact', fact_ids: ['calendar.next_high.time_utc'] }], risks: [] }),
    )
    assert.equal(r.rejected, 0, JSON.stringify(r.verdicts))
  })

  it('résumé : un chiffre absent du FactSheet rend le résumé invalide', () => {
    const r = validateAnalysis(FS, out({ summary: 'Probabilité de hausse de 64 %.' }))
    assert.equal(r.summaryOk, false)
    assert.equal(needsRetry(r), true)
  })

  it('au-delà de 30 % de rejets, un nouvel essai est demandé', () => {
    const r = validateAnalysis(
      FS,
      out({ claims: [{ text: 'RSI 71.', kind: 'fact', fact_ids: ['rvol.rvol'] }], risks: [{ text: 'OI 12 %.', kind: 'fact', fact_ids: ['rvol.rvol'] }] }),
    )
    assert.equal(needsRetry(r), true)
  })
})

function mockAnthropic(inputs: unknown[]): typeof fetch {
  let i = 0
  return (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body))
    assert.deepEqual(body.tool_choice, { type: 'tool', name: SUBMIT_ANALYSIS_TOOL.name })
    const input = inputs[Math.min(i++, inputs.length - 1)]
    return new Response(
      JSON.stringify({
        model: 'claude-test',
        content: input === null ? [] : [{ type: 'tool_use', name: 'submit_analysis', input }],
        usage: { input_tokens: 100, output_tokens: 50 },
      }),
      { status: 200 },
    )
  }) as typeof fetch
}

describe('runFactsheetAgent (LLM simulé)', () => {
  const base = { provider: 'anthropic' as const, apiKey: 'k', model: 'm', mode: 'explain_decision' as const, question: 'Pourquoi ?', factsheet: FS }

  it('réponse propre : 1 appel, claims gardés avec puces de faits', async () => {
    const r = await runFactsheetAgent({ ...base, fetchImpl: mockAnthropic([out()]) })
    assert.equal(r.attempts, 1)
    assert.equal(r.factsheet.removed, 0)
    assert.equal(r.factsheet.fallback, false)
    assert.equal(r.factsheet.claims[0].facts[0].id, 'rvol.rvol')
    assert.match(r.answer, /1,529/)
  })

  it('un chiffre inventé : claim retiré, réponse partielle signalée', async () => {
    const bad = out({ claims: [...out().claims, { text: 'RSI 71.', kind: 'fact', fact_ids: ['rvol.rvol'] }] })
    const r = await runFactsheetAgent({ ...base, fetchImpl: mockAnthropic([bad]) })
    assert.equal(r.attempts, 1) // 1/4 rejeté < 30 % : pas de nouvel essai
    assert.equal(r.factsheet.removed, 1)
    assert.doesNotMatch(r.answer, /71/)
    assert.match(r.answer, /Réponse partielle/)
  })

  it('trop de rejets : un seul nouvel essai, le meilleur est gardé', async () => {
    const bad = out({ summary: 'Hausse probable à 64 %.', claims: [{ text: 'RSI 71.', kind: 'fact', fact_ids: [] }], risks: [] })
    const r = await runFactsheetAgent({ ...base, fetchImpl: mockAnthropic([bad, out()]) })
    assert.equal(r.attempts, 2)
    assert.equal(r.factsheet.removed, 0)
  })

  it('sortie vide deux fois : faits bruts affichés, aucun texte LLM', async () => {
    const r = await runFactsheetAgent({ ...base, fetchImpl: mockAnthropic([null, null]) })
    assert.equal(r.attempts, 2)
    assert.equal(r.factsheet.fallback, true)
    assert.match(r.answer, /faits moteur bruts/)
    assert.match(r.answer, /rvol\.rvol : 1,529/)
  })

  it('OpenAI-compatible : function calling forcé', async () => {
    const fetchImpl = (async (url: RequestInfo | URL, init?: RequestInit) => {
      assert.match(String(url), /openrouter\.ai\/api\/v1\/chat\/completions/)
      const body = JSON.parse(String(init?.body))
      assert.deepEqual(body.tool_choice, { type: 'function', function: { name: 'submit_analysis' } })
      return new Response(
        JSON.stringify({
          model: 'or-test',
          choices: [{ message: { tool_calls: [{ function: { name: 'submit_analysis', arguments: JSON.stringify(out()) } }] } }],
          usage: { prompt_tokens: 10, completion_tokens: 5 },
        }),
        { status: 200 },
      )
    }) as typeof fetch
    const r = await runFactsheetAgent({ ...base, provider: 'openrouter', fetchImpl })
    assert.equal(r.factsheet.removed, 0)
    assert.equal(r.model, 'or-test')
  })
})

describe('helpers', () => {
  it('compactFacts expose display et absences', () => {
    const c = compactFacts(FS)
    assert.match(c, /rvol\.rvol = 1,529/)
    assert.match(c, /cvd\.delta = — .*\[unavailable: provider_no_taker_volume\]/)
  })

  it('parseAnalysis tolère une sortie partielle', () => {
    const p = parseAnalysis({ summary: 'x', claims: [{ text: 'a', kind: 'weird', fact_ids: [1] }] })
    assert.equal(p?.claims[0].kind, 'interpretation')
    assert.deepEqual(p?.claims[0].fact_ids, ['1'])
    assert.deepEqual(p?.risks, [])
  })

  it('renderAnswer liste les données indisponibles', () => {
    const r = renderAnswer(FS, out(), validateAnalysis(FS, out()))
    assert.deepEqual(r.missing, ['cvd.delta'])
    assert.match(r.text, /Données indisponibles : cvd\.delta/)
  })
})


// --- FS-0b : phrases littérales de la revue #171 (toutes doivent être REJETÉES) -----------------

const FS_B: FactSheet = {
  ...FS,
  facts: [
    ...FS.facts.filter((f) => f.id !== 'price.live'),
    fact('price.live', 83972.35, '83972,35', { source: 'provider' }),
    fact('fvg.active_count', 11, '11'),
    fact('location.poc', 83965.08333, '83965,08'),
    fact('location.val', 83684.66667, '83684,67'),
    fact('location.vah', 84918.5, '84918,5'),
    fact('pipeline.blocking_stages', 'location, regime', 'location, regime'),
    fact('location.price_vs_value_area', 'between_poc_vah', 'between_poc_vah'),
    fact('rel.price_vs_location_poc', 'au-dessus', 'au-dessus'),
    fact('rel.price_vs_location_vah', 'en dessous', 'en dessous'),
    fact('rel.price_vs_location_val', 'au-dessus', 'au-dessus'),
    fact('rsi.rsi', 58.2, '58,2'),
    fact('mtf_direction.higher_tf', '4h', '4h'),
    fact('calendar.next_high.minutes_to', 135, '135', { unit: 'min', source: 'calendar' }),
  ],
}

function rejects(text: string, fact_ids: string[], kind: Claim['kind'] = 'fact'): void {
  const r = validateAnalysis(FS_B, out({ claims: [{ text, kind, fact_ids }], risks: [] }))
  assert.equal(r.rejected, 1, `devait être rejeté : « ${text} »`)
}

describe('FS-0b — contournements de la revue #171', () => {
  it('V1 : jetons de date / pourcentages inventés', () => {
    rejects('Probabilité de rebond de 28 %', [], 'interpretation')
    rejects('Risque de baisse : 0 %', [], 'interpretation')
    rejects('Baisse possible de -28 %', [], 'interpretation')
  })
  it('V2 : résumé chiffré', () => {
    const r = validateAnalysis(FS_B, out({ summary: 'Le BTC vise 84 300 et pourrait prendre 11 % ; RSI 20.' }))
    assert.equal(r.summaryOk, false)
  })
  it('V3 : bande relative supprimée', () => rejects('Objectif à 84 300', ['price.live']))
  it('V4 : RSI 20 et « 850 M »', () => {
    rejects('RSI 20, zone de survente', ['rvol.rvol'])
    rejects('Volume de 850 M', ['rvol.rvol'])
  })
  it('V5 : arrondi grossier', () => rejects('Le RVOL est de 1', ['rvol.rvol']))
  it('V6 : unité / sens et citation massive', () => {
    rejects('Hausse attendue de 11 %', ['fvg.active_count'])
    rejects('Stop à 82 600, cible 84 800', FS_B.facts.map((f) => f.id))
  })
  it('V7 : nombres en toutes lettres', () =>
    rejects('Le prix devrait doubler, avec dix pour cent de hausse', [], 'interpretation'))
  it('V8 : causalité sur la décision sans étapes bloquantes', () => {
    rejects("NO_TRADE parce que VP3 n'a mesuré aucun edge", ['pipeline.decision'])
    const ok = validateAnalysis(FS_B, out({ claims: [{ text: 'NO_TRADE car les étapes location, regime échouent.', kind: 'fact', fact_ids: ['pipeline.decision', 'pipeline.blocking_stages'] }], risks: [] }))
    assert.equal(ok.rejected, 0, JSON.stringify(ok.verdicts))
  })
  it('V8 : « le prix entre X et Y » vérifié contre price.live', () => {
    rejects('Le prix évolue dans un HVN entre POC 83965,08 et VAL 83684,67', ['location.poc', 'location.val'])
    const ok = validateAnalysis(FS_B, out({ claims: [{ text: 'Le prix évolue entre POC 83965,08 et VAH 84918,5.', kind: 'fact', fact_ids: ['location.price_vs_value_area', 'location.poc', 'location.vah'] }], risks: [] }))
    assert.equal(ok.rejected, 0, JSON.stringify(ok.verdicts))
  })
  it('garde les cas légitimes', () => {
    const r = validateAnalysis(FS_B, out({ risks: [] }))
    assert.equal(r.rejected, 0, JSON.stringify(r.verdicts.filter((v) => !v.ok)))
  })
})


// --- FS-0c : contournements de 2e génération trouvés sur 0692694 (tous doivent être REJETÉS) ------

function summaryRejected(summary: string): void {
  const r = validateAnalysis(FS_B, out({ summary }))
  assert.equal(r.summaryOk, false, `résumé devait être rejeté : « ${summary} »`)
}

describe('FS-0c — timeframes, chiffres non ASCII, unités, bornes Unicode', () => {
  it('V1 : heure inventée masquée comme timeframe', () => rejects('Rebond attendu vers 12h.', [], 'scenario'))
  it('V4 : « 30m » (millions) masqué comme timeframe', () => rejects('Volume de 30m sur la séance.', [], 'interpretation'))
  it('V3 : chiffres pleine chasse', () => rejects('Objectif ８４ ３００.', [], 'scenario'))
  it('V3 : unité autre que % (points de base)', () => rejects('Hausse de 11 pb attendue.', ['fvg.active_count']))
  it('V3 : suffixes k / $ / x hors rvol', () => {
    rejects('Support vers 11k.', ['fvg.active_count'])
    rejects('Objectif 83972,35 $.', ['price.live'])
    rejects('Volume 11x la moyenne.', ['fvg.active_count'])
    const ok = validateAnalysis(FS_B, out({ claims: [{ text: 'Volume à 1,529x la moyenne.', kind: 'fact', fact_ids: ['rvol.rvol'] }], risks: [] }))
    assert.equal(ok.rejected, 0, JSON.stringify(ok.verdicts))
  })
  // V8 sémantique : gardé par ichivol-2c (FS-0c ne le traite pas) — phrases littérales de la 2e revue.
  it('V8 / N5 : causalité sur une décision nommée sans pipeline.decision cité', () =>
    rejects('NO_TRADE parce que le funding explose.', ['rvol.rvol']))
  it('V8 / N6 : « cours » au lieu de « prix »', () =>
    rejects('Le cours évolue entre POC 83965,08 et VAL 83684,67.', ['location.poc', 'location.val']))
  it('pas de faux positif : CVD en milliers à la précision exacte (prod)', () => {
    const fsC: FactSheet = { ...FS_B, facts: [...FS_B.facts, fact('cvd.rolling_delta', -1843.7, '-1843,7')] }
    const ok = validateAnalysis(fsC, out({ claims: [{ text: 'Le rolling delta CVD est de -1843,7.', kind: 'fact', fact_ids: ['cvd.rolling_delta'] }], risks: [] }))
    assert.equal(ok.rejected, 0, JSON.stringify(ok.verdicts))
    const bad = validateAnalysis(fsC, out({ claims: [{ text: 'Le rolling delta CVD est de -1844.', kind: 'fact', fact_ids: ['cvd.rolling_delta'] }], risks: [] }))
    assert.equal(bad.rejected, 1)
  })
  it('V8 : pas de faux positif « BELOW du kumo … score » (prod)', () => {
    const fsK: FactSheet = { ...FS_B, facts: [...FS_B.facts, fact('ichimoku.price_vs_kumo', 'BELOW', 'BELOW'), fact('ichimoku.score', -58.3333, '-58,3333')] }
    const r = validateAnalysis(fsK, out({ claims: [{ text: 'Ichimoku place le prix BELOW du kumo avec un score de -58,3333.', kind: 'fact', fact_ids: ['ichimoku.price_vs_kumo', 'ichimoku.score'] }], risks: [] }))
    assert.equal(r.rejected, 0, JSON.stringify(r.verdicts))
  })
  it('V8 / N10 : « au-dessus de la VAH » faux', () => {
    rejects('Le prix est au-dessus de la VAH 84918,5.', ['location.vah'])
    const ok = validateAnalysis(FS_B, out({ claims: [{ text: 'Le prix reste sous la VAH 84918,5.', kind: 'fact', fact_ids: ['rel.price_vs_location_vah', 'location.vah'] }], risks: [] }))
    assert.equal(ok.rejected, 0, JSON.stringify(ok.verdicts))
  })
  it('V2 : résumé avec 30m / 12h / pleine chasse / causalité « dû à »', () => {
    summaryRejected('Volume de 30m, rebond vers 12h.')
    summaryRejected('Le BTC vise ８４ ３００.')
    summaryRejected('NO_TRADE dû au funding.')
  })
  it('V7/V8 : bornes Unicode (« moitié », « dû à », « à cause »)', () => {
    rejects('La moitié du volume est vendeuse.', [], 'interpretation')
    rejects('NO_TRADE dû à un funding extrême.', ['pipeline.decision'], 'interpretation')
    rejects('NO_TRADE à cause du funding.', ['pipeline.decision'], 'interpretation')
  })
  it('garde les timeframes légitimes (FactSheet, fait cité, casse)', () => {
    const fs = { ...FS_B, facts: [...FS_B.facts, fact('mtf_direction.higher_tf', '4h', '4h')] }
    for (const [text, ids] of [
      ['En 1h, le RVOL est de 1,529.', ['rvol.rvol']],
      ['En 4h la direction est neutre ; RVOL 1,529 en 1H.', ['mtf_direction.higher_tf', 'rvol.rvol']],
      ['Prochain événement le 2026-09-29 04:30 UTC.', ['calendar.next_high.time_utc']],
    ] as const) {
      const r = validateAnalysis(fs, out({ claims: [{ text, kind: 'fact', fact_ids: [...ids] }], risks: [] }))
      assert.equal(r.rejected, 0, JSON.stringify(r.verdicts))
    }
    const s = validateAnalysis(fs, out({ summary: 'En 1h comme en 4h, le pipeline ne trade pas (NO_TRADE).' }))
    assert.equal(s.summaryOk, true, JSON.stringify(s.summaryErrors))
  })
})

// --- FS-0f : 3e sonde (ichivol-ce) — relations = faits moteur cités, jamais déduites ---------------

function accepts(text: string, fact_ids: string[], kind: Claim['kind'] = 'fact'): void {
  const r = validateAnalysis(FS_B, out({ claims: [{ text, kind, fact_ids }], risks: [] }))
  assert.equal(r.rejected, 0, `devait passer : « ${text} » ${JSON.stringify(r.verdicts.filter((v) => !v.ok).map((v) => v.errors))}`)
}

describe('FS-0f — sonde 3 : contournements (rejetés)', () => {
  it('X1 : 2e « au-dessus » non porté (VAH en dessous)', () =>
    rejects('Le prix est au-dessus du POC 83965,08 et au-dessus de la VAH 84918,5.', ['rel.price_vs_location_poc', 'location.poc', 'location.vah']))
  it('X2 / X3 : « dépasse », « au-delà » sans relation cohérente', () => {
    rejects('Le prix dépasse la VAH 84918,5.', ['location.vah'])
    rejects('Le prix évolue au-delà de la VAH 84918,5.', ['rel.price_vs_location_vah', 'location.vah'])
  })
  it('X4 : niveau loin dans la phrase', () =>
    rejects('Le prix se maintient au-dessus, avec un volume correct et une structure propre, de la VAH 84918,5.', ['location.vah']))
  it('X5 : sujet hors liste', () => rejects('La paire cote au-dessus de la VAH 84918,5.', ['location.vah']))
  it('X6 : négation', () => rejects("Le prix n'est pas sous la VAH 84918,5.", ['rel.price_vs_location_vah', 'location.vah']))
  it('X7 / X8 : causalité hors liste', () => {
    rejects("Le NO_TRADE s'explique par un funding extrême.", ['pipeline.decision'])
    rejects('Pas de trade suite au funding extrême.', ['rvol.rvol'], 'interpretation')
    rejects('Le pipeline bloque vu que le RVOL est faible.', ['rvol.rvol'], 'interpretation')
  })
})

describe('FS-0f — sonde 3 : phrases vraies (acceptées)', () => {
  it('L4 : « En H4 » avec higher_tf 4h cité', () => accepts('En H4, la direction reste neutre.', ['mtf_direction.higher_tf']))
  it('L5 : « RSI(14) à 58,2 »', () => accepts('Le RSI(14) est à 58,2.', ['rsi.rsi']))
  it('L6 : « dans 135 min » avec minutes_to cité', () =>
    accepts('Événement macro dans 135 min.', ['calendar.next_high.minutes_to']))
  it('L8 : prix entre VAL et VAH avec la relation citée', () =>
    accepts('Le prix évolue entre VAL 83684,67 et VAH 84918,5.', ['location.price_vs_value_area', 'location.val', 'location.vah']))
  it('forme positive de la relation', () =>
    accepts('Le prix est en dessous de la VAH 84918,5.', ['rel.price_vs_location_vah', 'location.vah']))
})
