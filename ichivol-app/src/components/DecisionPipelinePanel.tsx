import { labelPipelineGate } from '../lib/decisionLabels'
import {
  formatStageCodes,
  pipelineHeadline,
  pipelineReadingBlocks,
  stageStatusLabel,
  type DecisionPipelineView,
  type PipelineReadingBlock,
  type PipelineStage,
  type PipelineStageStatus,
} from '../lib/decisionPipeline'

function statusTone(status: PipelineStageStatus): string {
  switch (status) {
    case 'pass':
      return 'pass'
    case 'fail':
      return 'fail'
    case 'watch':
      return 'watch'
    case 'pending':
      return 'pending'
    case 'skip':
      return 'skip'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

function gateTone(gate: string): 'bull' | 'bear' | 'neutral' {
  if (gate === 'BUY') return 'bull'
  if (gate === 'SELL') return 'bear'
  return 'neutral'
}

function stageIndex(id: PipelineStage['id']): string {
  switch (id) {
    case 'direction':
      return '1'
    case 'participation':
      return '2'
    case 'structure':
      return '3'
    case 'location':
      return '4'
    case 'regime':
      return '5'
    default: {
      const _exhaustive: never = id
      return _exhaustive
    }
  }
}

function StageRow({ stage }: { stage: PipelineStage }) {
  const tone = statusTone(stage.status)
  const chips = formatStageCodes(stage.codes, 6)
  return (
    <li className={`pipeline-stage pipeline-stage--${tone}`}>
      <div className="pipeline-stage-top">
        <span className="pipeline-stage-index" aria-hidden>
          {stageIndex(stage.id)}
        </span>
        <div className="pipeline-stage-titles">
          <strong>{stage.label}</strong>
          <span className="pipeline-stage-q muted">{stage.question}</span>
        </div>
        <span className={`pipeline-stage-badge pipeline-stage-badge--${tone}`}>
          {stageStatusLabel(stage.status)}
        </span>
      </div>
      <p className="pipeline-stage-summary">{stage.summary}</p>
      {chips.length > 0 && (
        <div className="chip-row">
          {chips.map((c) => (
            <span key={c} className="sig-chip">
              {c}
            </span>
          ))}
        </div>
      )}
      {stage.status === 'pending' && (
        <span className="pipeline-stage-since muted">Prévu {stage.since.toUpperCase()}</span>
      )}
    </li>
  )
}

function ReadingCard({ block }: { block: PipelineReadingBlock }) {
  const tone = statusTone(block.status)
  return (
    <article className={`pipeline-reading-card pipeline-reading-card--${tone}`}>
      <header className="pipeline-reading-card-head">
        <strong>{block.title}</strong>
        <span className={`pipeline-stage-badge pipeline-stage-badge--${tone}`}>
          {stageStatusLabel(block.status)}
        </span>
      </header>
      <p className="pipeline-reading-body">{block.body}</p>
      {block.facts.length > 0 && (
        <ul className="pipeline-reading-facts">
          {block.facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
    </article>
  )
}

export function DecisionPipelinePanel({ view }: { view: DecisionPipelineView }) {
  const readings = pipelineReadingBlocks(view)

  return (
    <section className="decision-pipeline" aria-label="Pipeline de décision">
      <div className="decision-pipeline-head">
        <span className="subhead">Pipeline</span>
        <span className="pipeline-headline muted">{pipelineHeadline(view)}</span>
      </div>
      <p className="pipeline-legend muted">
        Direction → Participation → Structure → Location → Régime
        {view.native ? ' · moteur natif' : ' · vue adaptée'}
      </p>
      {view.native && view.gateDecision && (
        <div className="pipeline-gate-row">
          <span className="muted">Verdict portes</span>
          <span className={`bias bias-${gateTone(view.gateDecision)}`} title={view.gateDecision}>
            {labelPipelineGate(view.gateDecision)}
          </span>
        </div>
      )}
      {readings.length > 0 && (
        <div className="pipeline-readings">
          <span className="subhead">Lecture PA · MTF · Location · ATR</span>
          <div className="pipeline-readings-grid">
            {readings.map((b) => (
              <ReadingCard key={b.id} block={b} />
            ))}
          </div>
        </div>
      )}
      <ol className="pipeline-stages">
        {view.stages.map((s) => (
          <StageRow key={s.id} stage={s} />
        ))}
      </ol>
    </section>
  )
}
