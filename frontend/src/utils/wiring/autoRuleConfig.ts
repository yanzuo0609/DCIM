import type { NetworkNode } from '@/api/network'
import type { WiringRuleConfig } from '@/utils/wiringTypes'
import { resolveWiringDeviceType } from '@/utils/wiringDeviceType'

/**
 * 兼容旧自动规则：规则里残留的 1G/COPPER 不应把万兆交换机的 48 个
 * 10G DOWNLINK 全部过滤掉。以实际匹配到的源交换机模型类型校正规则速率。
 */
export function alignAutomaticAccessRuleToHardware(
  cfg: WiringRuleConfig,
  sources: NetworkNode[],
): WiringRuleConfig {
  if (cfg.connection_type !== 'ACCESS_ENDPOINT') return cfg
  if (String(cfg.allocation_mode || 'AUTO').toUpperCase() !== 'AUTO') return cfg
  // 显式规则分类优先于模型数量推断，避免同一拓扑同时存在千兆、万兆交换机时
  // 因多数表决把千兆规则纠正成万兆规则。
  if (cfg.rule_category === 'GIG_TO_ENDPOINT') {
    cfg.speed = '1G'
    cfg.port_speed = '1G'
    cfg.speed_mode = 'EXACT'
    cfg.port_media = 'COPPER'
    cfg.media = 'COPPER'
    cfg.source_port_purpose = 'DOWNLINK'
    cfg.target_port_purpose = cfg.target_port_purpose || 'SERVER'
    return cfg
  }
  if (cfg.rule_category === 'TEN_GIG_TO_ENDPOINT') {
    cfg.speed = '10G'
    cfg.port_speed = '10G'
    cfg.speed_mode = 'MIN'
    cfg.port_media = 'AUTO'
    if (cfg.media === 'COPPER') cfg.media = 'LC_LC_OM34'
    cfg.source_port_purpose = 'DOWNLINK'
    cfg.target_port_purpose = cfg.target_port_purpose || 'SERVER'
    return cfg
  }
  const types = sources.map(resolveWiringDeviceType)
  const tenGig = types.filter((type) => type === 'ACCESS_SWITCH_10G').length
  const gig = types.filter((type) => type === 'ACCESS_SWITCH_1G' || type === 'BMC_SWITCH').length
  if (!tenGig && !gig) return cfg

  if (tenGig >= gig) {
    cfg.speed = '10G'
    cfg.port_speed = '10G'
    cfg.speed_mode = 'MIN'
    if (String(cfg.port_media || '').toUpperCase() === 'COPPER') cfg.port_media = 'AUTO'
    if (cfg.media === 'COPPER') cfg.media = 'LC_LC_OM34'
  } else {
    cfg.speed = '1G'
    cfg.port_speed = '1G'
    cfg.speed_mode = 'EXACT'
    cfg.port_media = 'COPPER'
    cfg.media = 'COPPER'
  }
  cfg.source_port_purpose = 'DOWNLINK'
  cfg.target_port_purpose = cfg.target_port_purpose || 'SERVER'
  return cfg
}
