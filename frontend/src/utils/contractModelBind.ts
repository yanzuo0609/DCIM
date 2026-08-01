import type { DeviceContractSummary } from '@/api/contract'
import {
  createDeviceModel,
  createManufacturer,
  listDeviceModels,
  listManufacturers,
  type DeviceModel,
  type Manufacturer,
} from '@/api/device'

export function summaryOptionKey(row: DeviceContractSummary): string {
  return [row.manufacturer_name || '', row.device_name || '', row.device_model_name || ''].join('||')
}

export function formatSummaryOptionLabel(row: DeviceContractSummary): string {
  const parts = [
    row.manufacturer_name || '未知厂商',
    row.device_name || '未命名设备',
    row.device_model_name,
  ]
  if (row.purchase_quantity) parts.push(`采购×${row.purchase_quantity}`)
  if (row.linked_count) parts.push(`已关联台账×${row.linked_count}`)
  return parts.join(' · ')
}

function genModelCode(name: string) {
  const base = name
    .replace(/[^\w\u4e00-\u9fa5]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 24)
  return `M_${base || 'MODEL'}_${Date.now().toString(36).toUpperCase()}`.slice(0, 50)
}

function genMfgCode(name: string) {
  const base = name
    .replace(/[^\w\u4e00-\u9fa5]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 20)
  return `MFG_${base || 'CUSTOM'}`.slice(0, 50)
}

/** 确保合同汇总行对应的档案型号存在（与设备管理「从合同同步型号」一致） */
export async function resolveModelFromSummary(
  row: DeviceContractSummary,
  cache?: { models?: DeviceModel[]; manufacturers?: Manufacturer[] },
): Promise<DeviceModel> {
  const modelName = (row.device_model_name || '').trim()
  if (!modelName) throw new Error('合同汇总缺少型号名称')

  let models = cache?.models
  if (!models) {
    models = await listDeviceModels()
  }
  const mfgName = (row.manufacturer_name || '').trim()
  const hit = models.find(
    (m) =>
      m.name === modelName &&
      (!mfgName || !m.manufacturer_name || m.manufacturer_name === mfgName),
  )
  if (hit) return hit

  let manufacturers = cache?.manufacturers
  if (!manufacturers) {
    manufacturers = await listManufacturers({ page_size: 100 })
  }
  let manufacturerId = manufacturers.find((m) => m.name === (mfgName || '自定义'))?.id
  if (!manufacturerId) {
    const created = await createManufacturer({
      code: genMfgCode(mfgName || '自定义'),
      name: mfgName || '自定义',
    })
    manufacturerId = created.id
    manufacturers.push(created)
    if (cache) cache.manufacturers = manufacturers
  }

  const createdModel = await createDeviceModel({
    code: genModelCode(modelName),
    name: modelName,
    manufacturer_id: manufacturerId,
    height_u: 1,
    description: '来自网络设备定义 / 合同厂商型号采购汇总',
  })
  models.push(createdModel)
  if (cache) cache.models = models
  return createdModel
}
