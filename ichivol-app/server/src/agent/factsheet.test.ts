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
    risks: [{ text: 'Le prix (83703,35) reste sous le dernier sommet 83820.', kind: 'fact', fact_ids: ['price.live', 'structure.last_swing_high'] }],
    invalidation: [],
    missing_data: [],
    ...over,
  }
}

describe('extractNumbers', () => {
  it('lit FR/EN, %, et ignore timeframes et périodes', () => {
    assert.deepEqual(extractNumbers('Signaux NON_VALIDE (VP3), étape AG-S1, stratégie B7.'), [])
    const n = extractNumbers('RVOL 1,529 (93 %) en 1h, ATR 14 = 472.1, prix 83 703,35, Donchian 55/20')
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
    for (const text of ['RVOL 1,53', 'RVOL 1.529', 'RVOL environ 1,5']) {
      const r = validateAnalysis(FS, out({ claims: [{ text, kind: 'fact', fact_ids: ['rvol.rvol'] }], risks: [] }))
      assert.equal(r.rejected, 0, text)
    }
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
