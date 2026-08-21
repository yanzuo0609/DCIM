/** 合同 / 资产汇总 / 资产详细参数 / 设备管理 共用指标名称 */
export const ASSET_FIELD_LABELS = {
  deviceName: '设备名称',
  productModel: '产品型号',
  productVendor: '产品厂商',
  deviceType: '设备类型',
  typeClass: '类型归类',
} as const

export type AssetFieldKey = keyof typeof ASSET_FIELD_LABELS
