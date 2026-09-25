import type { useSettingsController } from './useSettingsController'
import { AlertsPanel } from './AlertsPanel'
import { ConnectionsPanel } from './ConnectionsPanel'
import { EnvironmentPanel } from './EnvironmentPanel'
import { LlmPanel } from './LlmPanel'
import { MarketPanel } from './MarketPanel'
import { RiskPanel } from './RiskPanel'

type Ctrl = ReturnType<typeof useSettingsController>

export function SettingsForm({ c }: { c: Ctrl }) {
  const { section, onSubmit } = c
  return (
    <form className="settings-form" onSubmit={onSubmit}>
      {section === 'llm' && <LlmPanel c={c} />}
      {section === 'connections' && <ConnectionsPanel c={c} />}
      {section === 'market' && <MarketPanel c={c} />}
      {section === 'alerts' && <AlertsPanel c={c} />}
      {section === 'risk' && <RiskPanel c={c} />}
      {section === 'environment' && <EnvironmentPanel c={c} />}
    </form>
  )
}
