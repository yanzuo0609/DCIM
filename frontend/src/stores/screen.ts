import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  defaultScreenLayout,
  loadScreenLayout,
  resetScreenLayout,
  saveScreenLayout,
  type ScreenLayoutConfig,
} from '@/utils/screenLayout'

const FEATURE_KEY = 'rackdcim.screen.feature.v1'

export interface ScreenFeatureState {
  /** 是否在侧栏显示「运营大屏」入口 */
  menuEnabled: boolean
}

function loadFeature(): ScreenFeatureState {
  try {
    const text = localStorage.getItem(FEATURE_KEY)
    if (!text) return { menuEnabled: true }
    const parsed = JSON.parse(text) as Partial<ScreenFeatureState>
    return { menuEnabled: parsed.menuEnabled !== false }
  } catch {
    return { menuEnabled: true }
  }
}

function persistFeature(state: ScreenFeatureState) {
  localStorage.setItem(FEATURE_KEY, JSON.stringify(state))
}

export const useScreenStore = defineStore('screen', () => {
  const menuEnabled = ref(loadFeature().menuEnabled)
  const layout = ref<ScreenLayoutConfig>(loadScreenLayout())

  const themeLabel = computed(() => {
    const map: Record<string, string> = {
      teal: '青绿驾驶舱',
      cyan: '深空青蓝',
      amber: '琥珀运维',
      violet: '紫晶智控',
      steel: '钢铁灰域',
    }
    return map[layout.value.theme] || layout.value.theme
  })

  function setMenuEnabled(enabled: boolean) {
    menuEnabled.value = enabled
    persistFeature({ menuEnabled: enabled })
  }

  function reloadLayout() {
    layout.value = loadScreenLayout()
  }

  function applyLayout(config: ScreenLayoutConfig) {
    layout.value = saveScreenLayout(config)
  }

  function restoreDefaultLayout() {
    layout.value = resetScreenLayout()
    return layout.value
  }

  function ensureDefaults() {
    if (!localStorage.getItem(FEATURE_KEY)) {
      persistFeature({ menuEnabled: menuEnabled.value })
    }
    if (!layout.value?.title) {
      layout.value = defaultScreenLayout()
    }
  }

  return {
    menuEnabled,
    layout,
    themeLabel,
    setMenuEnabled,
    reloadLayout,
    applyLayout,
    restoreDefaultLayout,
    ensureDefaults,
  }
})
