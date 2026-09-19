# IchiVol Evidence Architecture

**Status:** implemented as additive layer on Grand V2 (2026-09-19)  
**North star:** [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md)  
**Lab:** [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md)

## Pipeline

```text
MarketDataProvider (volume_type stamped)
        ↓
Indicators (Ichimoku · RVOL · Structure · ATR · Location · …)
        ↓
SignalContext (feature_version = signal_context_v1)
        ↓
EvidenceEngine.evaluate(context, catalog)
        ↓
DecisionEngine (pipeline gates + combiner MVP labels)
        ↓
PaperBroker (decision_id / evidence_id linkage)
        ↓
Outcome (MFE/MAE / forward returns)
        ↓
Evidence DB (signal_evidence)
```

## What EvidenceEngine does / does not do

| Does | Does not |
|------|----------|
| Historical matching on SignalContext features | Invent BUY/SELL |
| Sample-size quality (NO_DATA → VALID_SAMPLE) | Invent confidence % |
| Forward return / MFE / MAE distributions | Replace Strategy Lab |
| Explainable contradictions / why-not / invalidation | Call an LLM for signals |
| Persist audit trail | Live order routing |

Confidence in the combiner (`ichimoku × rvol`) remains an **MVP label**, explicitly marked as such in the UI. Historical `favorable_rate` is an **observation rate with N**, never presented as a predicted probability without sample_size.

## Volume semantics

`VolumeType`: `EXCHANGE_VOLUME` | `REPORTED_VOLUME` | `TICK_VOLUME` | `SYNTHETIC_VOLUME` | `NONE`

| Provider | Default |
|----------|---------|
| binance | EXCHANGE_VOLUME |
| biquote | TICK_VOLUME |
| twelve_data | REPORTED_VOLUME if volume > 0 else NONE |

RVOL on tick volume must not be read as exchange participation. Matching rejects cross-`volume_type` pairs by default.

## Key modules

| Module | Path |
|--------|------|
| VolumeType | `engine/app/market_data/volume_semantics.py` |
| SignalContext | `engine/app/evidence/context.py` |
| EvidenceEngine | `engine/app/evidence/engine.py` |
| Historical matching | `engine/app/evidence/matching.py` |
| In-window catalog | `engine/app/evidence/catalog.py` |
| Persistence | `engine/app/evidence/persistence.py` + `SignalEvidenceRecord` |
| UI card | `ichivol-app/src/components/SignalEvidenceCard.tsx` |

## Strategy Lab relationship

Event Study, Ablation, Walk-Forward remain in `app/strategy_lab/*`. EvidenceEngine can optionally embed their summaries; it does not re-implement them.
