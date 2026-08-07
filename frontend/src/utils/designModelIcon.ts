import type { NetworkNodeKind, ServerFormFactor, SwitchSubtype } from '@/api/network'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import { designCategoryToNodeKind, resolveDesignSwitchRole } from '@/utils/designModelToNode'

export interface DesignModelIconProps {
  kind: NetworkNodeKind
  switchSubtype: SwitchSubtype | null
  serverFormFactor: ServerFormFactor
  securityHeightU: number
}

/** 模型列表/属性旁的设备简图 logo 参数 */
export function designModelIconProps(model: NetworkDesignModel): DesignModelIconProps {
  const kind = designCategoryToNodeKind(model.category)
  const attrs = model.attributes || {}
  let switchSubtype: SwitchSubtype | null = null
  if (kind === 'switch') {
    if (model.subtype === 'switch' || model.category === 'network') {
      switchSubtype = resolveDesignSwitchRole(attrs)
    } else {
      switchSubtype = 'gigabit'
    }
  }
  const u = Math.max(1, Number(attrs.form_factor_u ?? model.height_u) || 1)
  const serverFormFactor: ServerFormFactor = u >= 4 ? 4 : u >= 2 ? 2 : 1
  return {
    kind,
    switchSubtype,
    serverFormFactor,
    securityHeightU: Math.max(1, Number(model.height_u) || 1),
  }
}
