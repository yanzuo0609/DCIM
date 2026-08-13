/**
 * 兼容门面：布线规则执行入口
 * 实现已迁移至 utils/wiring/（对齐 docs/18-rules_structured.md）
 */
export {
  applyWiringRule,
  applyWiringRuleLinks,
  previewWiringScenario,
  previewWiringPairs,
  listFreePortOptions,
  resolveScenario,
  SCENARIO_LABELS,
  type ScenarioId,
  type WiringApplyIssue,
  type WiringApplyReport,
  type WiringApplyResult,
  type ProposedPair,
  type WiringPreviewResult,
} from '@/utils/wiring/apply'
